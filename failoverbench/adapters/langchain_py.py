"""`langchain`: LangChain's ChatOpenAI with `.with_fallbacks([...])`.

Baseline: max_retries 2 and a 30 s timeout on each model, one fallback model.
LangChain documents that streaming fallbacks only cover errors raised before
the first chunk; what happens after that is exactly what S08/S09/S10/S14 measure.

params:
  max_retries: 2
  timeout_s: 30
"""

from __future__ import annotations

import time

from .base import Adapter, CallResult


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks
        out = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict) and block.get("type") in (None, "text") and block.get("text"):
                out.append(block["text"])
        return "".join(out)
    return "" if content is None else str(content)


def _usage(msg) -> dict | None:
    um = getattr(msg, "usage_metadata", None)
    if not um:
        return None
    return {"prompt_tokens": um.get("input_tokens"), "completion_tokens": um.get("output_tokens"),
            "total_tokens": um.get("total_tokens")}


class LangChainAdapter(Adapter):
    name = "langchain"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        from langchain_core.messages import HumanMessage  # imported lazily
        from langchain_openai import ChatOpenAI

        self._HumanMessage = HumanMessage
        self._ChatOpenAI = ChatOpenAI

    def _model(self, name: str):
        return self._ChatOpenAI(model=name, base_url=self.wall_base + "/v1", api_key="failoverbench",
                                max_retries=int(self.params.get("max_retries", 2)),
                                timeout=float(self.params.get("timeout_s", 30)), stream_usage=True)

    def _chain(self, primary: str, fallback: str | None):
        chain = self._model(primary)
        if fallback:
            chain = chain.with_fallbacks([self._model(fallback)])
        return chain

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        chain = self._chain(primary, fallback)
        lc_messages = [self._HumanMessage(content=m["content"]) for m in messages if m.get("role") == "user"]
        t0 = time.monotonic()
        elapsed = lambda: round(time.monotonic() - t0, 3)  # noqa: E731
        parts, usage, model, ttft, n = [], None, None, None, 0
        try:
            if stream:
                async for chunk in chain.astream(lc_messages):
                    n += 1
                    text = _text(getattr(chunk, "content", ""))
                    if text:
                        if ttft is None:
                            ttft = elapsed()
                        parts.append(text)
                    usage = _usage(chunk) or usage
                    rm = getattr(chunk, "response_metadata", None) or {}
                    model = rm.get("model_name") or rm.get("model") or model
                return CallResult(ok=True, content="".join(parts), reported_model=model, usage=usage,
                                  elapsed_s=elapsed(), ttft_s=ttft, chunks=n)
            r = await chain.ainvoke(lc_messages)
            rm = getattr(r, "response_metadata", None) or {}
            return CallResult(ok=True, content=_text(r.content), reported_model=rm.get("model_name") or rm.get("model"),
                              usage=_usage(r), elapsed_s=elapsed(), ttft_s=elapsed())
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            return CallResult(ok=False, status=status, error=f"{type(exc).__name__}: {str(exc)[:300]}", elapsed_s=elapsed(),
                              content="".join(parts), reported_model=model, usage=usage, ttft_s=ttft, chunks=n)
