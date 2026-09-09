"""Scoring rules that need no wall: the S12 context-retry discipline, the
partial re-run merge and the rescore pass. Runs under pytest or directly:

    python tests/test_scoring.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from failoverbench.runner import evaluate_check, load_yaml, merge_partial, rescore_doc  # noqa: E402

CATALOGUE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenarios", "catalogue.yaml")
CHECK = {"id": "no_blind_retry", "kind": "context_retry_discipline"}


def _discipline(attempts: int, sizes: list | None) -> str:
    m = {"outcome": "error", "attempts_primary": attempts, "primary_prompt_tokens": sizes}
    return evaluate_check(CHECK, m, {}, "full")["status"]


def test_context_retry_discipline():
    assert _discipline(1, [100]) == "pass"            # one attempt: ideal
    assert _discipline(2, [100, 60]) == "pass"        # a compacted retry is allowed
    assert _discipline(2, [100, 100]) == "fail"       # the same request again is not
    assert _discipline(2, [100, 140]) == "fail"
    assert _discipline(3, [100, 60, 60]) == "fail"    # every retry must shrink
    assert _discipline(2, None) == "fail"             # sizes unknown (older wall): counted as a resend
    assert _discipline(2, [100, None]) == "fail"


def _scenario(sid: str, verdict: str, **metrics) -> dict:
    m = {"outcome": "error", "complete": False, "error": "x", "elapsed_s": 1.0, "attempts_primary": 1,
         "attempts_fallback": 0, "alive_after": True, **metrics}
    return {"id": sid, "title": sid, "verdict": verdict, "reason": "", "checks": [], "metrics": m}


def test_merge_partial_keeps_order_and_records_the_rerun():
    cat = load_yaml(CATALOGUE)
    ids = [s["id"] for s in cat["scenarios"]]
    existing = {"scenarios": [_scenario(i, "safe") for i in ids], "summary": {}, "failoverbench": "old",
                "methodology": "0.1", "timing": {}, "system": {"name": "x"}}
    fresh = {"scenarios": [_scenario("S12", "pass", outcome="success", complete=True)], "failoverbench": "new",
             "methodology": "0.1", "timing": {"profile": "full"}, "system": {"name": "x", "label": "X"},
             "run_started_at": "2026-09-09T00:00:00+00:00", "run_seconds": 2.0}
    merged = merge_partial(existing, fresh, cat)
    assert [r["id"] for r in merged["scenarios"]] == ids
    assert next(r for r in merged["scenarios"] if r["id"] == "S12")["verdict"] == "pass"
    assert merged["summary"] == {"pass": 1, "partial": 0, "safe": len(ids) - 1, "fail": 0, "na": 0}
    assert merged["reruns"] == [{"ids": ["S12"], "run_started_at": "2026-09-09T00:00:00+00:00", "run_seconds": 2.0}]
    assert merged["failoverbench"] == "new" and merged["system"]["label"] == "X"


def test_rescore_recomputes_verdicts_from_stored_metrics():
    cat = load_yaml(CATALOGUE)
    # An S12 row stored as "fail" by an older rule, but whose metrics show one
    # attempt: the current rule scores it safe (clean error, nothing resent).
    doc = {"profile": "full", "system": {"name": "x", "capabilities": {"fallback": False}},
           "scenarios": [_scenario("S12", "fail", primary_prompt_tokens=[21])], "summary": {}}
    doc, changes = rescore_doc(doc, cat)
    assert changes == ["S12: fail -> safe"]
    assert doc["scenarios"][0]["verdict"] == "safe"
    assert doc["summary"]["safe"] == 1 and "rescored_at" in doc
    # Two attempts without recorded sizes stay a fail: the data cannot say it was a compaction.
    doc = {"profile": "full", "system": {"name": "x", "capabilities": {}},
           "scenarios": [_scenario("S12", "fail", attempts_primary=2)], "summary": {}}
    doc, changes = rescore_doc(doc, cat)
    assert changes == [] and doc["scenarios"][0]["verdict"] == "fail"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all scoring tests passed")
