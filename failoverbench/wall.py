"""The wall: a fake OpenAI-compatible provider that breaks on purpose.

Point any gateway or SDK at ``http://127.0.0.1:8401/v1`` and pick the fault
with the *model name*. ``fb-ok`` always answers; every ``fb-sNN-...`` model
misbehaves in one documented way (see ``scenarios/catalogue.yaml``).

It is a raw asyncio HTTP/1.1 server on purpose: a framework cannot reset a
TCP connection before headers, stall a stream with the socket open, or end a
chunked body without the terminating chunk. Those are the failures that
happen in the wild, so the wall has to be able to produce them exactly.

Control endpoints (never proxied through the system under test):

* ``POST /control/reset``   — clear the request log and attempt counters
* ``GET  /control/log``     — every request seen since reset, with timings
* ``POST /control/config``  — set timing profile (``{"profile": "fast"}``)
* ``GET  /control/health``  — liveness
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import struct
import sys
import time
from email.utils import formatdate

from . import CANONICAL_ANSWER, __version__

WORDS = CANONICAL_ANSWER.split()

# Timings the runner and the wall must agree on. "full" is what a real
# scorecard run uses; "fast" keeps a local test loop under two minutes.
TIMING_PROFILES = {
    "full": {
        "retry_after_s": 2.0,
        "slow_ttft_s": 20.0,
        "stall_s": 30.0,
        "no_response_s": 120.0,
        "flap_down_s": 60.0,
        "token_interval_ms": 15,
        "cut_after_tokens": 40,
        "stall_after_tokens": 20,
        "malformed_at_token": 10,
    },
    "fast": {
        "retry_after_s": 2.0,
        "slow_ttft_s": 3.0,
        "stall_s": 4.0,
        "no_response_s": 15.0,
        "flap_down_s": 6.0,
        "token_interval_ms": 5,
        "cut_after_tokens": 40,
        "stall_after_tokens": 20,
        "malformed_at_token": 10,
    },
}

REASONS = {
    100: "Continue", 200: "OK", 400: "Bad Request", 401: "Unauthorized",
    404: "Not Found", 429: "Too Many Requests", 500: "Internal Server Error",
    502: "Bad Gateway", 503: "Service Unavailable",
}

IDLE_TIMEOUT_S = 75.0
READ_LIMIT = 1 << 20  # 1 MiB request head / chunk limit

# model name -> behaviour tag. Gateways forward the upstream model name as
# configured, sometimes with a provider prefix ("openai/fb-s01-..."); we key
# on the "fb-<tag>" part after the last slash.
BEHAVIOURS = {
    "ok": "ok",
    "ok-noprefill": "ok_noprefill",
    "s01": "429_retry_after_once",
    "s02": "429_persistent",
    "s03": "500_once",
    "s04": "503_persistent",
    "s05": "reset_once",
    "s06": "no_response",
    "s07": "slow_ttft",
    "s08": "stream_cut",
    "s09": "stream_stall",
    "s10": "malformed_chunk",
    "s11": "no_done",
    "s12": "context_length",
    "s13": "content_filter",
    "s14": "stream_cut",      # same fault as S08; the *fallback* differs
    "s15": "flap",
    "s16": "503_persistent",  # same fault as S04; the *accounting* is scored
}


def tag_for(model: str) -> str | None:
    name = model.rsplit("/", 1)[-1].strip().lower()
    if not name.startswith("fb-"):
        return None
    rest = name[3:]
    if rest in ("ok", "ok-noprefill"):
        return rest
    tag = rest.split("-", 1)[0]
    return tag if tag in BEHAVIOURS else None


class Request:
    __slots__ = ("method", "path", "version", "headers", "body", "peer")

    def __init__(self, method, path, version, headers, body, peer):
        self.method, self.path, self.version = method, path, version
        self.headers, self.body, self.peer = headers, body, peer

    @property
    def keep_alive(self) -> bool:
        conn = self.headers.get("connection", "").lower()
        if self.version == "HTTP/1.0":
            return "keep-alive" in conn
        return "close" not in conn


class Wall:
    def __init__(self, timing: dict, verbose: bool = False):
        self.timing = dict(timing)
        self.verbose = verbose
        self.started_at = time.time()
        self.reset()

    # ----------------------------------------------------------------- state
    def reset(self):
        self.t0 = time.monotonic()
        self.log: list[dict] = []
        self.counts: dict[str, int] = {}
        self.seq = 0

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 4)

    def record(self, **fields) -> dict:
        entry = {"t": self.now(), **fields}
        self.log.append(entry)
        if self.verbose:
            print(json.dumps(entry), file=sys.stderr, flush=True)
        return entry

    def bump(self, model: str) -> int:
        self.counts[model] = self.counts.get(model, 0) + 1
        return self.counts[model]

    # ------------------------------------------------------------ connection
    async def handle_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        try:
            while True:
                req = await self.read_request(reader, writer, peer)
                if req is None:
                    break
                keep = await self.dispatch(req, reader, writer)
                if not keep:
                    break
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError,
                asyncio.LimitOverrunError, asyncio.TimeoutError):
            pass
        except Exception as exc:  # never let one bad request kill the wall
            self.record(action="wall-error", error=repr(exc))
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def read_request(self, reader, writer, peer) -> Request | None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=IDLE_TIMEOUT_S)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            return None
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, path, version = lines[0].split(" ", 2)
        except ValueError:
            return None
        headers: dict[str, str] = {}
        for ln in lines[1:]:
            if not ln:
                continue
            k, _, v = ln.partition(":")
            headers[k.strip().lower()] = v.strip()
        if headers.get("expect", "").lower() == "100-continue":
            writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
            await writer.drain()
        body = b""
        if "content-length" in headers:
            n = int(headers["content-length"])
            body = await reader.readexactly(n) if n else b""
        elif "chunked" in headers.get("transfer-encoding", "").lower():
            parts = []
            while True:
                size_line = await reader.readuntil(b"\r\n")
                size = int(size_line.split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while True:  # trailers
                        ln = await reader.readuntil(b"\r\n")
                        if ln == b"\r\n":
                            break
                    break
                parts.append(await reader.readexactly(size))
                await reader.readexactly(2)
            body = b"".join(parts)
        return Request(method, path, version, headers, body, peer)

    # --------------------------------------------------------------- writing
    @staticmethod
    def _head(status: int, headers: dict, keep: bool) -> bytes:
        base = {
            "Date": formatdate(usegmt=True),
            "Server": f"failoverbench-wall/{__version__}",
            "Connection": "keep-alive" if keep else "close",
        }
        base.update(headers)
        lines = [f"HTTP/1.1 {status} {REASONS.get(status, 'OK')}"]
        lines += [f"{k}: {v}" for k, v in base.items()]
        return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")

    async def send_json(self, writer, status: int, obj, keep: bool, extra: dict | None = None) -> bool:
        body = json.dumps(obj).encode()
        headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        if extra:
            headers.update(extra)
        writer.write(self._head(status, headers, keep) + body)
        await writer.drain()
        return keep

    async def send_error(self, writer, status: int, message: str, etype: str, code, keep: bool,
                         extra: dict | None = None, param=None) -> bool:
        return await self.send_json(
            writer, status,
            {"error": {"message": message, "type": etype, "param": param, "code": code}},
            keep, extra,
        )

    @staticmethod
    def _chunk(data: bytes) -> bytes:
        return f"{len(data):x}\r\n".encode() + data + b"\r\n"

    async def _rst(self, writer):
        """Abort the connection with a TCP RST instead of a FIN."""
        sock = writer.get_extra_info("socket")
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        except Exception:
            pass
        writer.close()

    # -------------------------------------------------------------- dispatch
    async def dispatch(self, req: Request, reader, writer) -> bool:
        keep = req.keep_alive
        path = req.path.split("?", 1)[0]
        if req.method == "POST" and path.endswith("/chat/completions"):
            return await self.chat(req, reader, writer, keep)
        if req.method == "GET" and path.endswith("/models"):
            models = [{"id": f"fb-{t}", "object": "model", "created": int(self.started_at), "owned_by": "failoverbench"}
                      for t in BEHAVIOURS]
            return await self.send_json(writer, 200, {"object": "list", "data": models}, keep)
        if path == "/control/reset":
            self.reset()
            return await self.send_json(writer, 200, {"ok": True, "t": self.now()}, keep)
        if path == "/control/log":
            return await self.send_json(writer, 200, {"t": self.now(), "timing": self.timing, "log": self.log}, keep)
        if path == "/control/config":
            try:
                cfg = json.loads(req.body or b"{}")
            except json.JSONDecodeError:
                return await self.send_error(writer, 400, "invalid JSON", "invalid_request_error", None, keep)
            if cfg.get("profile") in TIMING_PROFILES:
                self.timing = dict(TIMING_PROFILES[cfg["profile"]])
            for k, v in (cfg.get("timing") or {}).items():
                if k in self.timing:
                    self.timing[k] = type(self.timing[k])(v)
            return await self.send_json(writer, 200, {"ok": True, "timing": self.timing}, keep)
        if path in ("/", "/health", "/control/health"):
            return await self.send_json(writer, 200, {"ok": True, "wall": __version__, "t": self.now()}, keep)
        return await self.send_error(writer, 404, f"No route for {req.method} {path}", "invalid_request_error", None, keep)

    # ------------------------------------------------------------------ chat
    async def chat(self, req: Request, reader, writer, keep: bool) -> bool:
        try:
            body = json.loads(req.body or b"{}")
        except json.JSONDecodeError:
            return await self.send_error(writer, 400, "Request body is not valid JSON", "invalid_request_error", None, keep)
        model = str(req.headers.get("x-fb-model") or body.get("model") or "")
        tag = tag_for(model)
        stream = bool(body.get("stream", False))
        messages = body.get("messages") or []
        last = messages[-1] if messages else {}
        last_role = last.get("role")
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        attempt = self.bump(model)
        self.seq += 1
        entry = self.record(
            model=model, tag=tag, attempt=attempt, stream=stream, last_role=last_role,
            rid=req.headers.get("x-request-id") or req.headers.get("x-fb-run"),
            auth="authorization" in req.headers, client=f"{req.peer[0]}:{req.peer[1]}" if req.peer else None,
            action=None,
        )
        T = self.timing

        if tag is None:
            entry["action"] = "404 model_not_found"
            return await self.send_error(writer, 404, f"The model `{model}` does not exist", "invalid_request_error",
                                         "model_not_found", keep, param="model")

        behaviour = BEHAVIOURS[tag]

        # ---- prefill continuation: an assistant message last, whose content is
        # a prefix of the canonical answer, gets the remainder (like a real
        # provider that supports prefill). Anything else gets the full answer.
        words = WORDS
        continuation = False
        if last_role == "assistant":
            partial = (last.get("content") or "").strip()
            if behaviour == "ok_noprefill":
                entry["action"] = "400 prefill_rejected"
                return await self.send_error(
                    writer, 400,
                    "This model does not support assistant message prefill. The conversation must end with a user message.",
                    "invalid_request_error", "invalid_prefill", keep, param="messages")
            if partial and CANONICAL_ANSWER.startswith(partial):
                words = CANONICAL_ANSWER[len(partial):].split()
                continuation = True

        prompt_tokens = sum(len(str(m.get("content") or "").split()) + 4 for m in messages)
        entry["prompt_tokens"] = prompt_tokens  # lets the runner tell a compacted retry from a blind one

        # ---- the faults -----------------------------------------------------
        if behaviour in ("ok", "ok_noprefill"):
            pass
        elif behaviour == "429_retry_after_once":
            if attempt == 1:
                entry["action"] = f"429 retry-after={T['retry_after_s']:g}"
                return await self.send_error(writer, 429, f"Rate limit reached for {model}. Please retry after {T['retry_after_s']:g} seconds.",
                                             "rate_limit_error", "rate_limit_exceeded", keep,
                                             {"Retry-After": f"{int(T['retry_after_s'])}"})
        elif behaviour == "429_persistent":
            entry["action"] = "429"
            return await self.send_error(writer, 429, f"Rate limit reached for {model}.", "rate_limit_error",
                                         "rate_limit_exceeded", keep)
        elif behaviour == "500_once":
            if attempt == 1:
                entry["action"] = "500"
                return await self.send_error(writer, 500, "The server had an error while processing your request.",
                                             "server_error", None, keep)
        elif behaviour == "503_persistent":
            entry["action"] = "503"
            return await self.send_error(writer, 503, "The engine is currently overloaded. Please try again later.",
                                         "server_error", "overloaded", keep)
        elif behaviour == "reset_once":
            if attempt == 1:
                entry["action"] = "tcp-reset"
                await self._rst(writer)
                return False
        elif behaviour == "no_response":
            entry["action"] = f"no-response {T['no_response_s']:g}s"
            gave_up = await self._wait_or_client_gone(reader, T["no_response_s"])
            entry["client_gave_up_at"] = gave_up
            return False
        elif behaviour == "context_length":
            entry["action"] = "400 context_length_exceeded"
            return await self.send_error(writer, 400,
                                         "This model's maximum context length is 8192 tokens. However, your messages resulted in 9631 tokens. Please reduce the length of the messages.",
                                         "invalid_request_error", "context_length_exceeded", keep, param="messages")
        elif behaviour == "content_filter":
            entry["action"] = "400 content_policy_violation"
            return await self.send_error(writer, 400, "Your request was rejected as a result of our safety system.",
                                         "invalid_request_error", "content_policy_violation", keep)
        elif behaviour == "flap":
            if self.now() < T["flap_down_s"]:
                entry["action"] = "503 (down window)"
                return await self.send_error(writer, 503, "The engine is currently overloaded. Please try again later.",
                                             "server_error", "overloaded", keep)
            entry["action"] = "200 (recovered)"

        # ---- healthy or stream-shaped faults --------------------------------
        mode = {"slow_ttft": "slow", "stream_cut": "cut", "stream_stall": "stall",
                "malformed_chunk": "malformed", "no_done": "no_done"}.get(behaviour, "ok")
        if stream:
            return await self.stream_answer(writer, model, keep, words, continuation, mode, include_usage,
                                            prompt_tokens, entry)
        return await self.plain_answer(writer, model, keep, words, continuation, mode, prompt_tokens, entry)

    async def _wait_or_client_gone(self, reader, seconds: float):
        """Sleep up to `seconds`; return the time at which the client hung up, else None."""
        t_start = self.now()
        eof = asyncio.create_task(reader.read(1))
        timer = asyncio.create_task(asyncio.sleep(seconds))
        done, pending = await asyncio.wait({eof, timer}, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
        if eof in done:
            return round(self.now() - t_start, 3)
        return None

    def _completion(self, rid: str, model: str, text: str, prompt_tokens: int, n_words: int) -> dict:
        return {
            "id": rid, "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": n_words,
                      "total_tokens": prompt_tokens + n_words},
        }

    async def plain_answer(self, writer, model, keep, words, continuation, mode, prompt_tokens, entry) -> bool:
        T = self.timing
        text = (" " if continuation else "") + " ".join(words)
        rid = f"chatcmpl-fb-{self.seq}"
        if mode == "slow":
            entry["action"] = f"200 after {T['slow_ttft_s']:g}s"
            await asyncio.sleep(T["slow_ttft_s"])
        obj = self._completion(rid, model, text, prompt_tokens, len(words))
        body = json.dumps(obj).encode()
        if mode == "cut":
            # Declare the full length, send 60% of it, then hang up.
            n = int(len(body) * 0.6)
            entry["action"] = f"200 truncated body {n}/{len(body)}B then close"
            writer.write(self._head(200, {"Content-Type": "application/json", "Content-Length": str(len(body))}, False) + body[:n])
            await writer.drain()
            writer.close()
            return False
        if mode == "stall":
            entry["action"] = f"200 headers then silence {T['stall_s']:g}s then close"
            writer.write(self._head(200, {"Content-Type": "application/json", "Content-Length": str(len(body))}, False))
            await writer.drain()
            await asyncio.sleep(T["stall_s"])
            writer.close()
            return False
        if mode == "malformed":
            bad = body[: len(body) // 2] + b'"oops'  # syntactically invalid JSON body
            entry["action"] = "200 malformed JSON body"
            writer.write(self._head(200, {"Content-Type": "application/json", "Content-Length": str(len(bad))}, keep) + bad)
            await writer.drain()
            return keep
        if entry.get("action") is None:
            entry["action"] = "200"
        return await self.send_json(writer, 200, obj, keep)

    async def stream_answer(self, writer, model, keep, words, continuation, mode, include_usage, prompt_tokens, entry) -> bool:
        T = self.timing
        rid = f"chatcmpl-fb-{self.seq}"
        created = int(time.time())
        interval = T["token_interval_ms"] / 1000.0

        def chunk(delta, finish=None, usage=None, choices=True):
            obj = {"id": rid, "object": "chat.completion.chunk", "created": created, "model": model,
                   "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if choices else []}
            if usage is not None:
                obj["usage"] = usage
            return obj

        async def sse(obj_or_raw) -> None:
            raw = obj_or_raw if isinstance(obj_or_raw, bytes) else f"data: {json.dumps(obj_or_raw)}\n\n".encode()
            writer.write(self._chunk(raw))
            await writer.drain()

        writer.write(self._head(200, {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache",
                                      "Transfer-Encoding": "chunked", "X-Accel-Buffering": "no"}, keep))
        await writer.drain()
        if mode == "slow":
            entry["action"] = f"200 stream, first token after {T['slow_ttft_s']:g}s"
            await asyncio.sleep(T["slow_ttft_s"])
        await sse(chunk({"role": "assistant", "content": ""}))
        sent = 0
        for i, w in enumerate(words):
            if mode == "cut" and i == T["cut_after_tokens"]:
                entry["action"] = f"200 stream cut after {i} tokens (no terminating chunk)"
                writer.close()
                return False
            if mode == "stall" and i == T["stall_after_tokens"]:
                entry["action"] = f"200 stream stalled after {i} tokens for {T['stall_s']:g}s then close"
                await asyncio.sleep(T["stall_s"])
                writer.close()
                return False
            if mode == "malformed" and i == T["malformed_at_token"]:
                entry["action"] = f"200 stream with malformed chunk at token {i}"
                await sse(b'data: {"id": "' + rid.encode() + b'", "object": "chat.completion.chunk", "choices": [{"delta": {"content": \n\n')
            text = (" " + w) if (i > 0 or continuation) else w
            await sse(chunk({"content": text}))
            sent += 1
            if interval:
                await asyncio.sleep(interval)
        await sse(chunk({}, finish="stop"))
        if include_usage:
            await sse(chunk({}, usage={"prompt_tokens": prompt_tokens, "completion_tokens": sent,
                                       "total_tokens": prompt_tokens + sent}, choices=False))
        if mode == "no_done":
            entry["action"] = "200 stream complete, [DONE] omitted"
        else:
            await sse(b"data: [DONE]\n\n")
            if entry.get("action") is None:
                entry["action"] = "200 stream"
        writer.write(b"0\r\n\r\n")
        await writer.drain()
        return keep


async def serve(host: str, port: int, profile: str, verbose: bool):
    wall = Wall(TIMING_PROFILES[profile], verbose=verbose)
    server = await asyncio.start_server(wall.handle_conn, host, port, limit=READ_LIMIT, reuse_address=True)
    print(f"failoverbench wall {__version__} listening on http://{host}:{port}/v1  (profile={profile})", file=sys.stderr, flush=True)
    async with server:
        await server.serve_forever()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="failoverbench wall", description="Start the fake provider that breaks on purpose.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8401)
    ap.add_argument("--profile", choices=sorted(TIMING_PROFILES), default="full")
    ap.add_argument("--verbose", "-v", action="store_true", help="print every request as JSON to stderr")
    args = ap.parse_args(argv)
    try:
        asyncio.run(serve(args.host, args.port, args.profile, args.verbose))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
