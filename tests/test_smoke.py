"""Smoke test: start a wall on a free port, run the reference client through a
few scenarios, and assert the verdicts. Runs under pytest or directly:

    python tests/test_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from failoverbench import CANONICAL_ANSWER  # noqa: E402
from failoverbench.adapters import make_adapter  # noqa: E402
from failoverbench.runner import WallControl, load_yaml, run_scenario  # noqa: E402
from failoverbench.wall import TIMING_PROFILES, Wall  # noqa: E402

CATALOGUE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenarios", "catalogue.yaml")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _run(system_adapter: str, wanted: dict[str, str], params: dict | None = None) -> dict[str, dict]:
    port = free_port()
    wall = Wall(TIMING_PROFILES["fast"])
    server = await asyncio.start_server(wall.handle_conn, "127.0.0.1", port, limit=1 << 20)
    base = f"http://127.0.0.1:{port}"
    control = WallControl(base)
    cat = load_yaml(CATALOGUE)
    adapter = make_adapter(system_adapter, params or {}, base)
    await adapter.start()
    out = {}
    try:
        timing = await control.config("fast")
        for sc in cat["scenarios"]:
            if sc["id"] in wanted:
                out[sc["id"]] = await run_scenario(adapter, adapter.capabilities, control, sc, cat, "fast", timing)
    finally:
        await adapter.close()
        await control.close()
        server.close()
        await server.wait_closed()
    return out


def test_canonical_answer_is_sixty_words():
    assert len(CANONICAL_ANSWER.split()) == 60


def test_reference_client_passes_core_scenarios():
    wanted = {"S01": "pass", "S05": "pass", "S08": "pass", "S12": "pass", "S13": "pass", "S14": "pass"}
    res = asyncio.run(_run("reference", wanted))
    for sid, expect in wanted.items():
        assert res[sid]["verdict"] == expect, (sid, res[sid]["verdict"], res[sid]["reason"], res[sid]["checks"])
    assert res["S01"]["metrics"]["first_gap_s"] >= 1.8
    assert res["S12"]["metrics"]["attempts_primary"] == 1


def test_direct_client_is_safe_not_rescued():
    wanted = {"S02": "safe", "S08": "safe", "S13": "pass"}
    res = asyncio.run(_run("direct", wanted))
    for sid, expect in wanted.items():
        assert res[sid]["verdict"] == expect, (sid, res[sid]["verdict"], res[sid]["reason"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
