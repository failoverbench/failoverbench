"""`endpoint`: any OpenAI-compatible gateway reachable at a base URL.

The gateway owns retries and fallbacks; the adapter just asks it once and
reports what came back. Configure the gateway so that each scenario's model
name (e.g. `fb-s01-429-retry-after`) routes to the wall with `fb-ok` as its
fallback, or provide `model_map` to translate scenario models to whatever
names the gateway exposes. `python -m failoverbench litellm-config` writes a
ready-made LiteLLM proxy config from the catalogue.

params:
  base_url:   http://127.0.0.1:4000/v1
  api_key:    sk-anything
  headers:    {x-portkey-config: "..."}      # optional extra headers
  model_map:  {fb-s01-429-retry-after: s01}  # optional
"""

from __future__ import annotations

import httpx

from .base import Adapter, CallResult
from .http_common import call_chat


class EndpointAdapter(Adapter):
    name = "endpoint"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        self.client = httpx.AsyncClient()
        self.base_url = self.params["base_url"].rstrip("/")
        self.api_key = self.params.get("api_key", "failoverbench")
        self.headers = self.params.get("headers") or {}
        self.model_map = self.params.get("model_map") or {}

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        model = self.model_map.get(primary, primary)
        timeout = httpx.Timeout(connect=10.0, read=float(deadline_s), write=10.0, pool=10.0)
        return await call_chat(self.client, self.base_url, model, messages, stream=stream, api_key=self.api_key,
                               headers=self.headers, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()
