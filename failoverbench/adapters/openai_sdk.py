"""`openai-python`: the official OpenAI Python SDK with its built-in retries.

The SDK has no fallback concept, so `capabilities.fallback` is false and every
fail-over check is reported as n/a rather than a failure. What is scored is
whether the SDK honours Retry-After, bounds its attempts, never hangs, and
never presents a truncated stream as success.

params:
  max_retries: 2      # SDK default
  timeout_s: 30       # SDK default is 600s; a scorecard run needs a bound
"""

from __future__ import annotations

import time

from .base import Adapter, CallResult


class OpenAIPythonAdapter(Adapter):
    name = "openai-python"
    capabilities = {"fallback": False, "streaming": True}

    async def start(self) -> None:
        from openai import AsyncOpenAI  # imported lazily: not installed in every environment

        self.client = AsyncOpenAI(
            base_url=self.wall_base + "/v1",
            api_key="failoverbench",
            max_retries=int(self.params.get("max_retries", 2)),
            timeout=float(self.params.get("timeout_s", 30)),
        )

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        t0 = time.monotonic()
        elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731
        try:
            if stream:
                s = await self.client.chat.completions.create(
                    model=primary, messages=messages, stream=True, stream_options={"include_usage": True})
                parts, usage, model, ttft, n = [], None, None, None, 0
                async for chunk in s:
                    n += 1
                    model = getattr(chunk, "model", None) or model
                    if getattr(chunk, "usage", None):
                        usage = chunk.usage.model_dump()
                    for ch in chunk.choices or []:
                        text = getattr(ch.delta, "content", None) if ch.delta else None
                        if text:
                            if ttft is None:
                                ttft = elapsed()
                            parts.append(text)
                return CallResult(ok=True, content="".join(parts), reported_model=model, usage=usage,
                                  elapsed_s=elapsed(), ttft_s=ttft, chunks=n)
            r = await self.client.chat.completions.create(model=primary, messages=messages)
            return CallResult(ok=True, content=r.choices[0].message.content or "", reported_model=r.model,
                              usage=r.usage.model_dump() if r.usage else None, elapsed_s=elapsed(), ttft_s=elapsed())
        except Exception as exc:  # the SDK raises a family of APIError subclasses
            status = getattr(exc, "status_code", None)
            code = None
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                err = body.get("error") if isinstance(body.get("error"), dict) else body
                code = err.get("code") if isinstance(err, dict) else None
            return CallResult(ok=False, status=status, error_code=code,
                              error=f"{type(exc).__name__}: {str(exc)[:300]}", elapsed_s=elapsed())

    async def close(self) -> None:
        await self.client.close()
