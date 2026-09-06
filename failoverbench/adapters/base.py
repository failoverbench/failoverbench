"""Adapter interface: one class per system under test.

An adapter knows how to send a chat completion through a particular system
(an SDK, an in-process router, or an external gateway at a URL) and returns
what the *caller* of that system would see. The runner never looks inside
the system; it combines the adapter's view with the wall's request log.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict


@dataclass
class CallResult:
    ok: bool
    content: str = ""
    reported_model: str | None = None
    usage: dict | None = None
    error: str | None = None
    error_code: str | None = None
    status: int | None = None
    retry_after: float | None = None
    hang: bool = False
    elapsed_s: float = 0.0
    ttft_s: float | None = None
    chunks: int = 0
    bad_chunks: int = 0
    done_seen: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_error_body(body: bytes | str) -> tuple[str, str | None]:
    """Return (message, code) from an OpenAI-style error body, tolerating junk."""
    try:
        obj = json.loads(body)
        err = obj.get("error") if isinstance(obj, dict) else None
        if isinstance(err, dict):
            return str(err.get("message") or err), err.get("code")
        return str(obj)[:200], None
    except Exception:
        text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
        return text[:200] or "(empty body)", None


class Adapter:
    """Base class. Subclasses set `name` and `capabilities` and implement `complete`."""

    name = "base"
    capabilities = {"fallback": False, "streaming": True}

    def __init__(self, params: dict, wall_base: str):
        self.params = params or {}
        self.wall_base = wall_base.rstrip("/")

    async def start(self) -> None:  # optional
        return None

    async def complete(self, primary: str, fallback: str | None, stream: bool,
                       messages: list[dict], deadline_s: float) -> CallResult:
        raise NotImplementedError

    async def close(self) -> None:  # optional
        return None

    def describe(self) -> dict:
        return {"adapter": self.name, "capabilities": dict(self.capabilities), "params": self.params}


class Stopwatch:
    def __init__(self):
        self.t0 = time.monotonic()

    def __call__(self) -> float:
        return round(time.monotonic() - self.t0, 3)
