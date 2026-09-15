"""`litellm-router`: LiteLLM's in-process Router with retries and fallbacks.

One Router per (primary, fallback) pair, cached for the scenario so that
cooldown / circuit state persists across a sequence (S15).

params (all optional, passed through to litellm.Router):
  num_retries: 2
  timeout_s: 30
  allowed_fails: 1
  cooldown_time: 30
  context_window_fallbacks: true   # also register the fallback for context-length errors
  enable_mid_stream_fallback_continuation: false
  prefill_capable_models: [fb-ok]  # see start(): declares the capability the flag above filters on
"""

from __future__ import annotations

import time

from .base import Adapter, CallResult


class LiteLLMRouterAdapter(Adapter):
    name = "litellm-router"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        import litellm  # imported lazily: not installed in every environment
        import openai  # a litellm dependency; needed to tell real HTTP statuses apart
        from litellm import Router

        self._openai = openai
        litellm.suppress_debug_info = True
        litellm.drop_params = True
        # Mid-stream fallback continuation (LiteLLM PR #41127) chooses its
        # continuation target with a pre-call filter that asks the *model cost
        # map* whether the deployment's `litellm_params["model"]` declares
        # `supports_assistant_prefill`; a deployment's own `model_info` block is
        # never read. The wall's model names are not in the map, and a missing
        # declaration reads as "cannot prefill", so a model we want treated as
        # prefill-capable has to be registered into the map by name.
        for m in self.params.get("prefill_capable_models") or []:
            litellm.register_model({f"openai/{m}": {"litellm_provider": "openai", "mode": "chat",
                                                    "supports_assistant_prefill": True}})
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
        for k in ("allowed_fails", "cooldown_time", "retry_after", "routing_strategy",
                  "enable_mid_stream_fallback_continuation"):
            if k in self.params:
                kwargs[k] = self.params[k]
        self._routers[key] = self._Router(**kwargs)
        return self._routers[key]

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        router = self._router(primary, fallback)
        t0 = time.monotonic()
        elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731
        # Kept outside the try so that a stream which dies mid-answer still
        # reports what the caller had received (first token, chunks, model).
        parts, usage, model, ttft, n = [], None, None, None, 0
        try:
            if stream:
                resp = await router.acompletion(model="primary", messages=messages, stream=True,
                                                stream_options={"include_usage": True})
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
            # litellm stamps synthetic status codes on transport-level failures
            # (APIConnectionError -> 500, Timeout -> 408). Only record a status
            # the provider actually returned, as the openai-python adapter does.
            status = None if isinstance(exc, self._openai.APIConnectionError) else getattr(exc, "status_code", None)
            return CallResult(ok=False, status=status, error=f"{type(exc).__name__}: {str(exc)[:300]}", elapsed_s=elapsed(),
                              content="".join(parts), reported_model=model, usage=usage, ttft_s=ttft, chunks=n)

    async def close(self) -> None:
        self._routers.clear()
