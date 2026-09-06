"""`reference`: a small, deliberately boring client that does the right thing.

It exists so the checks can be validated against a known-good implementation
and so the scorecard has a "what correct looks like" row. Policy:

* 429            -> honour Retry-After (capped), else exponential backoff with jitter
* 5xx / reset / incomplete stream -> retry on the same provider, then fail over
* timeout / no first token         -> fail over immediately (a silent provider stays silent)
* 400 context_length_exceeded      -> no retry; next candidate
* 400 content_policy_violation     -> no retry; no fail-over; propagate
* other 4xx                        -> no retry; next candidate
* fail-over restarts the request without assistant prefill
"""

from __future__ import annotations

import asyncio
import random
import time

import httpx

from .base import Adapter, CallResult
from .http_common import call_chat

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class ReferenceAdapter(Adapter):
    name = "reference"
    capabilities = {"fallback": True, "streaming": True}

    async def start(self) -> None:
        self.client = httpx.AsyncClient()
        p = self.params
        self.max_attempts = int(p.get("max_attempts", 3))
        self.base_backoff_s = float(p.get("base_backoff_s", 0.5))
        self.max_backoff_s = float(p.get("max_backoff_s", 8.0))
        self.retry_after_cap_s = float(p.get("retry_after_cap_s", 10.0))
        self.connect_timeout_s = float(p.get("connect_timeout_s", 5.0))
        self.stall_limit_s = float(p.get("stall_limit_s", 10.0))
        self.ttft_limit_s = float(p.get("ttft_limit_s", 10.0))

    async def complete(self, primary, fallback, stream, messages, deadline_s) -> CallResult:
        candidates = [primary] + ([fallback] if fallback else [])
        started = time.monotonic()
        last: CallResult | None = None
        attempts_total = 0
        for model in candidates:
            for attempt in range(1, self.max_attempts + 1):
                remaining = deadline_s - (time.monotonic() - started)
                if remaining <= 0.5:
                    break
                timeout = httpx.Timeout(connect=self.connect_timeout_s, read=self.stall_limit_s, write=10.0, pool=10.0)
                r = await call_chat(self.client, self.wall_base + "/v1", model, messages, stream=stream,
                                    timeout=timeout, ttft_limit_s=self.ttft_limit_s)
                attempts_total += 1
                r.elapsed_s = round(time.monotonic() - started, 3)
                if r.ok:
                    return r
                last = r
                # ---- classify -------------------------------------------------
                if r.status is not None and 400 <= r.status < 500 and r.status not in RETRYABLE_STATUS:
                    if r.error_code == "content_policy_violation":
                        return r          # the same request will be rejected anywhere
                    break                 # no retry on 4xx; try the next candidate
                is_timeout = r.status is None and r.error and ("Timeout" in r.error or "ttft limit" in r.error)
                if is_timeout:
                    break                 # a silent provider stays silent; move on
                if attempt >= self.max_attempts:
                    break
                if r.status == 429 and r.retry_after is not None:
                    delay = min(r.retry_after, self.retry_after_cap_s)
                else:
                    delay = min(self.base_backoff_s * (2 ** (attempt - 1)), self.max_backoff_s)
                    delay *= 0.8 + 0.4 * random.random()
                await asyncio.sleep(min(delay, max(0.0, remaining - 0.5)))
        if last is None:
            return CallResult(ok=False, error="no candidates", elapsed_s=round(time.monotonic() - started, 3))
        last.error = f"{last.error} (after {attempts_total} attempt(s) across {len(candidates)} candidate(s))"
        return last

    async def close(self) -> None:
        await self.client.aclose()
