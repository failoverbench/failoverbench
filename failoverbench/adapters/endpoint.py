"""`endpoint`: any OpenAI-compatible gateway reachable at a base URL.

The gateway owns retries and fallbacks; the adapter asks it once and reports
what came back. Three ways to tell the gateway which model is primary and
which is the fallback, all driven from `systems/<name>.yaml`:

* the gateway's own config routes each scenario model to the wall with its
  fallback (LiteLLM proxy: `python -m failoverbench litellm-config`);
* `extra_body` — fields merged into the request body, with `{primary}` and
  `{fallback}` placeholders, already in `model_format` form (Bifrost:
  `fallbacks: ["{fallback}"]` becomes `["fake/fb-ok"]`);
* `headers_json` — a header whose value is a JSON document built from a dict
  with the same placeholders (Portkey: `x-portkey-config`).

`model_format` rewrites the model name the gateway sees (Bifrost wants a
provider prefix: `fake/{model}`). When a call has no fallback (the alive
probe), every list item or dict entry that mentions `{fallback}` is dropped,
so a two-target config naturally becomes a one-target config.

params:
  base_url:      http://127.0.0.1:4000/v1
  api_key:       sk-anything
  model_format:  "{model}"                     # optional
  model_map:     {fb-s01-429-retry-after: s01}  # optional, applied before model_format
  headers:       {x-foo: bar}                  # optional, string values templated
  headers_json:  {x-portkey-config: {...}}     # optional, dict → JSON string, templated
  extra_body:    {fallbacks: ["{fallback}"]}   # optional, templated
"""

from __future__ import annotations

import json

import httpx

from .base import Adapter, CallResult
from .http_common import call_chat

_DROP = object()


def mentions_fallback(node) -> bool:
    if isinstance(node, str):
        return "{fallback}" in node
    if isinstance(node, list):
        return any(mentions_fallback(x) for x in node)
    if isinstance(node, dict):
        return any(mentions_fallback(v) for v in node.values())
    return False


def fill(node, primary: str, fallback: str | None, model: str):
    """Substitute placeholders; drop any list item / dict entry that needs a
    fallback when there is none."""
    if isinstance(node, str):
        if fallback is None and "{fallback}" in node:
            return _DROP
        return node.replace("{primary}", primary).replace("{fallback}", fallback or "").replace("{model}", model)
    if isinstance(node, list):
        out = []
        for item in node:
            if fallback is None and mentions_fallback(item):
                continue
            value = fill(item, primary, fallback, model)
            if value is not _DROP:
                out.append(value)
        return out
    if isinstance(node, dict):
        # A list item is a unit (a Portkey target, a Bifrost fallback entry) and is
        # dropped whole; a dict entry is only dropped when its own value is a
        # string that needs the fallback — nested containers are pruned inside.
        out = {}
        for key, item in node.items():
            value = fill(item, primary, fallback, model)
            if value is not _DROP:
                out[key] = value
        return out
    return node


class EndpointAdapter(Adapter):
    name = "endpoint"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        self.client = httpx.AsyncClient()
        self.base_url = self.params["base_url"].rstrip("/")
        self.api_key = self.params.get("api_key", "failoverbench")
        self.model_format = self.params.get("model_format", "{model}")
        self.model_map = self.params.get("model_map") or {}
        self.headers = self.params.get("headers") or {}
        self.headers_json = self.params.get("headers_json") or {}
        self.extra_body = self.params.get("extra_body") or {}

    def _shape(self, primary: str, fallback: str | None) -> tuple[str, dict, dict]:
        model = self.model_format.replace("{model}", self.model_map.get(primary, primary))
        fb = None if fallback is None else self.model_format.replace("{model}", self.model_map.get(fallback, fallback))
        headers = {k: fill(v, model, fb, model) for k, v in self.headers.items()}
        for k, doc in self.headers_json.items():
            headers[k] = json.dumps(fill(doc, model, fb, model), separators=(",", ":"))
        extra = fill(self.extra_body, model, fb, model)
        return model, headers, extra

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        model, headers, extra = self._shape(primary, fallback)
        timeout = httpx.Timeout(connect=10.0, read=float(deadline_s), write=10.0, pool=10.0)
        return await call_chat(self.client, self.base_url, model, messages, stream=stream, api_key=self.api_key,
                               headers=headers, extra_body=extra, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()
