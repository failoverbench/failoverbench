"""`direct`: no gateway at all. One request straight at the provider, no retries.

This is the control row of the scorecard: what your app gets with zero
protection. Everything else is measured against it.
"""

from __future__ import annotations

import httpx

from .base import Adapter, CallResult
from .http_common import call_chat


class DirectAdapter(Adapter):
    name = "direct"
    capabilities = {"fallback": False, "streaming": True}

    async def start(self) -> None:
        self.client = httpx.AsyncClient()

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        timeout = httpx.Timeout(connect=5.0, read=float(self.params.get("read_timeout_s", 30)), write=10.0, pool=10.0)
        return await call_chat(self.client, self.wall_base + "/v1", primary, messages, stream=stream, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()
