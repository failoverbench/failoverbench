"""The three chart renderers produce PNGs from real result documents (skipped
without matplotlib). Runs under pytest or directly:

    python tests/test_charts.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(ROOT, "scenarios", "catalogue.yaml")

try:
    import matplotlib  # noqa: F401
    HAVE_MPL = True
except ImportError:  # pragma: no cover
    HAVE_MPL = False


def _fake_doc(name: str, verdicts: dict) -> dict:
    from failoverbench.runner import load_yaml
    cat = load_yaml(CATALOGUE)
    scenarios = []
    for s in cat["scenarios"]:
        v = verdicts.get(s["id"], "pass")
        m = {"outcome": "success" if v in ("pass", "partial") else "error", "complete": v in ("pass", "partial"),
             "elapsed_s": 130.0 if v == "fail" else 1.0, "attempts_primary": 1, "attempts_fallback": 1,
             "wall_actions": ["0.00s fb-s06-no-response #1 -> no-response 120s", "120.01s fb-s06-no-response #2 -> no-response 120s"]
             if v == "fail" else ["0.01s fb-ok #1 -> 200 stream"]}
        scenarios.append({"id": s["id"], "title": s["title"], "fallback_model": "fb-ok", "verdict": v, "reason": "", "checks": [], "metrics": m})
    return {"failoverbench": "0.2.0", "methodology": "0.1", "profile": "full", "run_started_at": "2026-09-12T10:00:00+00:00",
            "system": {"name": name, "label": name, "capabilities": {"fallback": True}, "notes": ""},
            "summary": {v: sum(1 for r in scenarios if r["verdict"] == v) for v in ("pass", "partial", "safe", "fail", "na")},
            "scenarios": scenarios}


def test_charts_render():
    if not HAVE_MPL:
        print("skipped: matplotlib not installed")
        return
    from failoverbench.charts import explainer_png, scorecard_png, timeline_png
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "results", "full"))
        a = _fake_doc("reference", {})
        b = _fake_doc("bifrost", {"S06": "fail", "S01": "partial", "S08": "safe"})
        for d in (a, b):
            with open(os.path.join(tmp, "results", "full", f"{d['system']['name']}.json"), "w") as fh:
                json.dump(d, fh)
        out = scorecard_png(os.path.join(tmp, "results"), "full", CATALOGUE, os.path.join(tmp, "s.png"), "12 Sep 2026")
        assert os.path.getsize(out) > 20_000
        out = timeline_png("S06", [b, a], CATALOGUE, os.path.join(tmp, "t.png"), "before / after", labels=["before", "after"])
        assert os.path.getsize(out) > 10_000
        out = explainer_png(os.path.join(tmp, "e.png"))
        assert os.path.getsize(out) > 10_000


if __name__ == "__main__":
    test_charts_render()
    print("ok  test_charts_render")
    print("all chart tests passed")
