"""`litellm-router`: LiteLLM's in-process Router with retries and fallbacks.

One Router per (primary, fallback) pair, cached for the scenario so that
cooldown / circuit state persists across a sequence (S15).

params (all optional, passed through to litellm.Router):
  num_retries: 2
  timeout_s: 30
  allowed_fails: 1
  cooldown_time: 30
  context_window_fallbacks: true   # also register the fallback for context-length errors
"""

from __future__ import annotations

import time

from .base import Adapter, CallResult


class LiteLLMRouterAdapter(Adapter):
    name = "litellm-router"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        import litellm  # imported lazily: not installed in every environment
        from litellm import Router

        litellm.suppress_debug_info = True
        litellm.drop_params = True
        self._Router = Router
        self._routers: dict[tuple, object] = {}

    def _router(self, primary: str, fallback: str | None):
        key = (primary, fallback)
        if key in self._routers:
            return self._routers[key]
        base = self.wall_base + "/v1"
        model_list = [{"model_name": "primary",
                       "litellm_params": {"model": "openai/" + primary, "api_base": base, "api_key": "failoverbench"}}]
        kwargs: dict = {
            "model_list": model_list,
            "num_retries": int(self.params.get("num_retries", 2)),
            "timeout": float(self.params.get("timeout_s", 30)),
            "set_verbose": False,
        }
        if fallback:
            model_list.append({"model_name": "fallback",
                               "litellm_params": {"model": "openai/" + fallback, "api_base": base, "api_key": "failoverbench"}})
            kwargs["fallbacks"] = [{"primary": ["fallback"]}]
            if self.params.get("context_window_fallbacks", True):
                kwargs["context_window_fallbacks"] = [{"primary": ["fallback"]}]
        for k in ("allowed_fails", "cooldown_time", "retry_after", "routing_strategy"):
            if k in self.params:
                kwargs[k] = self.params[k]
        self._routers[key] = self._Router(**kwargs)
        return self._routers[key]

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        router = self._router(primary, fallback)
        t0 = time.monotonic()
        elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731
        try:
            if stream:
                resp = await router.acompletion(model="primary", messages=messages, stream=True,
                                                stream_options={"include_usage": True})
                parts, usage, model, ttft, n = [], None, None, None, 0
                async for chunk in resp:
                    n += 1
                    model = getattr(chunk, "model", None) or model
                    u = getattr(chunk, "usage", None)
                    if u:
                        usage = u.model_dump() if hasattr(u, "model_dump") else dict(u)
                    for ch in getattr(chunk, "choices", None) or []:
                        delta = getattr(ch, "delta", None)
                        text = getattr(delta, "content", None) if delta else None
                        if text:
                            if ttft is None:
                                ttft = elapsed()
                            parts.append(text)
                return CallResult(ok=True, content="".join(parts), reported_model=model, usage=usage,
                                  elapsed_s=elapsed(), ttft_s=ttft, chunks=n)
            r = await router.acompletion(model="primary", messages=messages)
            u = getattr(r, "usage", None)
            return CallResult(ok=True, content=r.choices[0].message.content or "", reported_model=getattr(r, "model", None),
                              usage=(u.model_dump() if hasattr(u, "model_dump") else dict(u)) if u else None,
                              elapsed_s=elapsed(), ttft_s=elapsed())
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            return CallResult(ok=False, status=status, error=f"{type(exc).__name__}: {str(exc)[:300]}", elapsed_s=elapsed())

    async def close(self) -> None:
        self._routers.clear()
