"""One OpenAI-compatible chat call over httpx, streaming or not, parsed the
way a careful client would parse it. Shared by the direct, endpoint and
reference adapters."""

from __future__ import annotations

import asyncio
import json
import time

import httpx

from .base import CallResult, parse_error_body


async def call_chat(client: httpx.AsyncClient, base_url: str, model: str, messages: list[dict], *,
                    stream: bool, api_key: str = "failoverbench", headers: dict | None = None,
                    timeout: httpx.Timeout | float | None = None, ttft_limit_s: float | None = None,
                    lenient_chunks: bool = True) -> CallResult:
    url = base_url.rstrip("/") + "/chat/completions"
    hdrs = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    payload: dict = {"model": model, "messages": messages}
    t0 = time.monotonic()
    elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731

    if not stream:
        try:
            resp = await client.post(url, json=payload, headers=hdrs, timeout=timeout)
        except httpx.HTTPError as exc:
            return CallResult(ok=False, error=f"{type(exc).__name__}: {exc}", elapsed_s=elapsed())
        if resp.status_code != 200:
            msg, code = parse_error_body(resp.content)
            ra = resp.headers.get("retry-after")
            return CallResult(ok=False, status=resp.status_code, error=f"HTTP {resp.status_code}: {msg}", error_code=code,
                              retry_after=float(ra) if ra and ra.isdigit() else None, elapsed_s=elapsed())
        try:
            obj = resp.json()
        except ValueError:
            return CallResult(ok=False, status=200, error="HTTP 200 with malformed JSON body", elapsed_s=elapsed())
        try:
            content = obj["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            return CallResult(ok=False, status=200, error="HTTP 200 without choices[0].message", elapsed_s=elapsed())
        return CallResult(ok=True, content=content, reported_model=obj.get("model"), usage=obj.get("usage"),
                          elapsed_s=elapsed(), ttft_s=elapsed())

    payload["stream"] = True
    payload["stream_options"] = {"include_usage": True}
    parts: list[str] = []
    usage = None
    reported = None
    ttft = None
    chunks = 0
    bad = 0
    done = False
    try:
        async with client.stream("POST", url, json=payload, headers=hdrs, timeout=timeout) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                msg, code = parse_error_body(body)
                ra = resp.headers.get("retry-after")
                return CallResult(ok=False, status=resp.status_code, error=f"HTTP {resp.status_code}: {msg}", error_code=code,
                                  retry_after=float(ra) if ra and ra.isdigit() else None, elapsed_s=elapsed())
            lines = resp.aiter_lines()
            while True:
                if ttft is None and ttft_limit_s is not None:
                    remaining = ttft_limit_s - (time.monotonic() - t0)
                    if remaining <= 0:
                        return CallResult(ok=False, error=f"no first token within {ttft_limit_s:g}s (ttft limit)",
                                          elapsed_s=elapsed(), chunks=chunks)
                    try:
                        line = await asyncio.wait_for(lines.__anext__(), timeout=remaining)
                    except asyncio.TimeoutError:
                        return CallResult(ok=False, error=f"no first token within {ttft_limit_s:g}s (ttft limit)",
                                          elapsed_s=elapsed(), chunks=chunks)
                    except StopAsyncIteration:
                        break
                else:
                    try:
                        line = await lines.__anext__()
                    except StopAsyncIteration:
                        break
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    bad += 1
                    if lenient_chunks:
                        continue
                    return CallResult(ok=False, status=200, error="malformed SSE chunk", elapsed_s=elapsed(),
                                      chunks=chunks, bad_chunks=bad, content="".join(parts))
                chunks += 1
                reported = obj.get("model") or reported
                if obj.get("usage"):
                    usage = obj["usage"]
                for ch in obj.get("choices") or []:
                    delta = ch.get("delta") or {}
                    text = delta.get("content")
                    if text:
                        if ttft is None:
                            ttft = elapsed()
                        parts.append(text)
    except httpx.HTTPError as exc:
        return CallResult(ok=False, error=f"{type(exc).__name__}: {exc}", elapsed_s=elapsed(), chunks=chunks,
                          bad_chunks=bad, content="".join(parts), ttft_s=ttft)
    return CallResult(ok=True, content="".join(parts), reported_model=reported, usage=usage, elapsed_s=elapsed(),
                      ttft_s=ttft, chunks=chunks, bad_chunks=bad, done_seen=done)
