"""`dsh`: DeepSeek Harness with the dsh-llm-fallbacks plugin, driven through the
official Python SDK (`deepseek-harness-sdk`, JSON-RPC over stdio).

EXPERIMENTAL. DSH is a developer preview that changes weekly; this adapter
was written against the SDK docs of 8 Sep 2026 (deepseek-harness-sdk
0.1.2rc1, dsh-llm-fallbacks 0.4.2) and has not been run in the cloud sandbox.
Run `gateways/dsh/setup.sh` first: it prepares two harness homes, one whose
fallback chain ends in `fb-ok` and one whose chain ends in `fb-ok-noprefill`
(S14), because the chain lives in settings, not in the request.

What is measured is the harness as a caller would use it: the SDK's `run()`
with a plain prompt; the answer text, the provider/model that produced the
last assistant message, its usage, and the finish reason. DSH always sends its
own system prompt and tool roster; the wall ignores both.

Sequence scenarios (S15) reuse one harness *process* per (primary, fallback)
pair so the plugin's circuit state persists, but by default every request gets
a fresh session id: on the first run (8 Sep 2026) a shared session showed
one primary attempt and then nineteen answers from the fallback, including
five after the primary had recovered, which could be the harness keeping the
replaced model on the session rather than the plugin never probing. Set
`session_per_request: false` to reproduce the shared-session behaviour.

params:
  dsh_home:            gateways/dsh/home-default
  dsh_home_noprefill:  gateways/dsh/home-noprefill
  workspace:           gateways/dsh/workspace
  provider:            fake
  request_timeout_s:   60
  session_per_request: true
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid

from .base import Adapter, CallResult


class DSHAdapter(Adapter):
    name = "dsh"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        from deepseek_harness import DeepSeekHarness  # imported lazily

        self._Harness = DeepSeekHarness
        self._harnesses: dict = {}
        self._sessions: dict = {}
        self.provider = self.params.get("provider", "fake")
        self.workspace = os.path.abspath(self.params.get("workspace", "gateways/dsh/workspace"))
        os.makedirs(self.workspace, exist_ok=True)
        os.environ.setdefault("FAKE_API_KEY", "failoverbench")

    def _home_for(self, fallback: str | None) -> str:
        key = "dsh_home_noprefill" if fallback and "noprefill" in fallback else "dsh_home"
        return os.path.abspath(self.params.get(key, f"gateways/dsh/{'home-noprefill' if key.endswith('noprefill') else 'home-default'}"))

    def _harness(self, primary: str, fallback: str | None):
        home = self._home_for(fallback)
        key = (home, primary)
        if key not in self._harnesses:
            h = self._Harness(dsh_home=home, cwd=self.workspace, provider=self.provider, model=primary,
                              request_timeout_seconds=float(self.params.get("request_timeout_s", 60)))
            h.__enter__()
            self._harnesses[key] = h
            self._sessions[key] = f"fb-{uuid.uuid4().hex[:8]}"
        return self._harnesses[key], self._sessions[key]

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        prompt = messages[-1]["content"]
        t0 = time.monotonic()
        elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731
        first_delta = {"t": None, "n": 0}

        def on_notification(note):
            first_delta["n"] += 1
            if first_delta["t"] is None:
                text = str(note)
                if "delta" in text or "text" in text or "content" in text:
                    first_delta["t"] = elapsed()

        def run_sync():
            h, session_id = self._harness(primary, fallback)
            if self.params.get("session_per_request", True):
                session_id = f"fb-{uuid.uuid4().hex[:8]}"
            return h.run(prompt, session_id=session_id, on_notification=on_notification)

        try:
            r = await asyncio.to_thread(run_sync)
        except Exception as exc:
            return CallResult(ok=False, error=f"{type(exc).__name__}: {str(exc)[:300]}", elapsed_s=elapsed())

        events = list(getattr(r, "events", None) or [])
        last_msg = None
        for ev in events:
            if isinstance(ev, dict) and ev.get("type") == "assistant/message":
                last_msg = ev
        source = usage = None
        if last_msg:
            data = last_msg.get("data") or {}
            msg = data.get("message") or {}
            source = msg.get("source") or data.get("source")
            u = data.get("usage") or msg.get("usage")
            if isinstance(u, dict):
                usage = {"prompt_tokens": u.get("inputTokens"), "completion_tokens": u.get("outputTokens"),
                         "total_tokens": u.get("totalTokens")}
        reported = None
        if isinstance(source, dict) and source.get("model"):
            reported = f"{source.get('provider', '')}/{source['model']}".strip("/")
        finish = getattr(r, "finish_reason", None)
        text = getattr(r, "final_response", None) or ""
        if finish == "error" or not text:
            return CallResult(ok=False, error=f"dsh finish_reason={finish!r}, final_response={'empty' if not text else 'present'}",
                              elapsed_s=elapsed(), content=text, reported_model=reported, usage=usage,
                              ttft_s=first_delta["t"], chunks=first_delta["n"])
        return CallResult(ok=True, content=text, reported_model=reported, usage=usage, elapsed_s=elapsed(),
                          ttft_s=first_delta["t"] or elapsed(), chunks=first_delta["n"])

    async def close(self) -> None:
        for h in self._harnesses.values():
            try:
                h.__exit__(None, None, None)
            except Exception:
                pass
        self._harnesses.clear()
