"""The endpoint adapter's placeholder filling: `{primary}` / `{fallback}` /
`{model}` substitution, and dropping fallback-bearing entries when a call has
no fallback (the alive probe).

    python tests/test_templating.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from failoverbench.adapters.endpoint import fill  # noqa: E402

PORTKEY = {
    "strategy": {"mode": "fallback"},
    "targets": [
        {"provider": "openai", "override_params": {"model": "{primary}"}, "retry": {"attempts": 2}},
        {"provider": "openai", "override_params": {"model": "{fallback}"}},
    ],
}
BIFROST = {"fallbacks": ["fake/{fallback}"]}


def test_substitution_with_fallback():
    out = fill(PORTKEY, "fb-s01", "fb-ok", "fb-s01")
    assert out["targets"][0]["override_params"]["model"] == "fb-s01"
    assert out["targets"][1]["override_params"]["model"] == "fb-ok"
    assert fill(BIFROST, "fake/fb-s01", "fake/fb-ok", "fake/fb-s01") == {"fallbacks": ["fake/fake/fb-ok"]}
    assert fill("fake/{model}", "x", "y", "fb-s08") == "fake/fb-s08"


def test_fallback_entries_dropped_without_fallback():
    out = fill(PORTKEY, "fb-ok", None, "fb-ok")
    assert len(out["targets"]) == 1 and out["targets"][0]["override_params"]["model"] == "fb-ok"
    assert fill(BIFROST, "fake/fb-ok", None, "fake/fb-ok") == {"fallbacks": []}
    assert fill({"a": "{fallback}", "b": "{primary}"}, "p", None, "p") == {"b": "p"}


if __name__ == "__main__":
    test_substitution_with_fallback()
    test_fallback_entries_dropped_without_fallback()
    print("ok  templating")
