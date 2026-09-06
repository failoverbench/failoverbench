"""The runner: push one system through every scenario and score it.

For each scenario: reset the wall, make the call through the adapter under a
hard deadline (a hang is a result, not an exception), pull the wall's request
log, compute metrics from both views, evaluate the catalogue's checks, then
probe the system with a healthy request to see whether it is still alive.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import sys
import time

import httpx
import yaml

from . import CANONICAL_ANSWER, __version__
from .adapters import CallResult, make_adapter

WS = re.compile(r"\s+")


def norm(text: str | None) -> str:
    return WS.sub(" ", (text or "").strip())


CANON = norm(CANONICAL_ANSWER)


def tagkey(model: str | None) -> str:
    return (model or "").rsplit("/", 1)[-1].strip().lower()


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class WallControl:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def health(self) -> dict:
        return (await self.client.get(self.base + "/control/health")).json()

    async def reset(self) -> None:
        await self.client.post(self.base + "/control/reset")

    async def config(self, profile: str) -> dict:
        r = await self.client.post(self.base + "/control/config", json={"profile": profile})
        return r.json()["timing"]

    async def log(self) -> dict:
        return (await self.client.get(self.base + "/control/log")).json()

    async def close(self) -> None:
        await self.client.aclose()


# --------------------------------------------------------------------- checks
def evaluate_check(check: dict, m: dict, caps: dict, profile: str) -> dict:
    kind = check["kind"]
    cid = check.get("id", kind)
    req = check.get("requires")
    value = check.get("fast_value", check.get("value")) if profile == "fast" else check.get("value")

    def out(ok: bool | None, detail: str) -> dict:
        if ok is None:
            status = "na"
        elif ok:
            status = "pass"
        elif check.get("informational"):
            status = "info"
        else:
            status = "fail"
        return {"id": cid, "kind": kind, "status": status, "detail": detail,
                "severity": check.get("severity", "required"), "informational": bool(check.get("informational"))}

    if req and not caps.get(req):
        return out(None, f"n/a — system declares no {req}")

    oc = m["outcome"]
    if kind == "no_hang":
        return out(oc != "hang", f"ended in {m['elapsed_s']:.1f}s ({oc})" if oc != "hang" else f"HANG: {m.get('error')}")
    if kind == "outcome":
        exp = check["expect"]
        ok = {"success": oc == "success", "error": oc == "error", "success_or_error": oc in ("success", "error")}[exp]
        detail = oc if oc == "success" else f"{oc}: {m.get('error')}"
        return out(ok, detail)
    if kind == "complete":
        ok = oc == "success" and m["complete"]
        return out(ok, "complete answer" if ok else ("truncated/altered answer" if oc == "success" else oc))
    if kind == "no_truncated_success":
        bad = oc == "success" and not m["complete"]
        return out(not bad, f"success with {len(norm(m.get('content')).split())}/60 words" if bad else
                   ("complete answer" if oc == "success" else f"no success claimed ({oc})"))
    if kind == "attempts_primary_min":
        return out(m["attempts_primary"] >= value, f"{m['attempts_primary']} primary attempt(s)")
    if kind == "attempts_primary_max":
        return out(m["attempts_primary"] <= value, f"{m['attempts_primary']} primary attempt(s)")
    if kind == "attempts_primary_eq":
        return out(m["attempts_primary"] == value, f"{m['attempts_primary']} primary attempt(s)")
    if kind == "attempts_fallback_min":
        return out(m["attempts_fallback"] >= value, f"{m['attempts_fallback']} fallback attempt(s)")
    if kind == "attempts_fallback_max":
        return out(m["attempts_fallback"] <= value, f"{m['attempts_fallback']} fallback attempt(s)")
    if kind == "first_gap_min_s":
        gap = m["first_gap_s"]
        return out(gap is not None and gap >= value, f"gap {gap:.2f}s" if gap is not None else "no second attempt")
    if kind == "max_attempts_within":
        window = check["window_s"]
        times = m["primary_times"]
        n = sum(1 for t in times if t - times[0] < window) if times else 0
        return out(n <= value, f"{n} attempt(s) in first {window:g}s")
    if kind == "wall_max_s":
        return out(oc != "hang" and m["elapsed_s"] <= value, f"{m['elapsed_s']:.1f}s")
    if kind == "alive_after":
        return out(m["alive_after"], "healthy call succeeded afterwards" if m["alive_after"] else f"healthy call failed afterwards: {m.get('alive_error')}")
    if kind == "fallback_used":
        return out(m["attempts_fallback"] >= 1, f"{m['attempts_fallback']} fallback attempt(s)")
    if kind == "reported_model_is_fallback":
        if m["attempts_fallback"] == 0:
            return out(None, "n/a — the fallback was never used")
        rm = tagkey(m.get("reported_model"))
        fb = tagkey(m.get("fallback_model"))
        return out(bool(rm) and fb in rm, f"response.model = {m.get('reported_model')!r}")
    if kind == "usage_present":
        u = m.get("usage")
        return out(bool(u), f"usage = {u}" if u else "no usage block")
    if kind == "no_prefill_masking":
        masked = oc == "error" and m["prefill_rejections"] > 0
        return out(not masked, f"{m['prefill_rejections']} prefill rejection(s) at the fallback; final outcome {oc}")
    if kind == "seq_no_hang":
        return out(m["seq_hangs"] == 0, f"{m['seq_hangs']} hung request(s) of {len(m['seq_items'])}")
    if kind == "seq_served_during_outage":
        n, tot = m["seq_served_during_down"], m["seq_requests_during_down"]
        return out(tot > 0 and n == tot, f"{n}/{tot} requests answered while primary was down")
    if kind == "seq_recovered_within_s":
        rec = m["seq_recovered_after_s"]
        return out(rec is not None and rec <= value,
                   f"primary answered again {rec:+.1f}s after recovery" if rec is not None else "primary never used again after recovery")
    if kind == "seq_probe_discipline":
        n, tot = m["seq_primary_attempts_during_down"], m["seq_requests_during_down"]
        return out(n <= tot, f"{n} primary attempt(s) for {tot} request(s) during the outage")
    return out(False, f"unknown check kind {kind}")


def verdict_for(sc: dict, checks: list[dict], m: dict) -> tuple[str, str]:
    """Return (verdict, reason).

    pass    rescued (ideal outcome reached), every check clean
    partial rescued, but an advisory check failed — or, for ideal=error, the system
            answered anyway by routing around the rejection
    safe    not rescued, but a bounded clean error and every required check clean
    fail    a required check failed, a hang, or a truncated answer presented as success
    """
    oc = m["outcome"]
    ideal = sc.get("ideal", "success")
    if oc == "hang":
        return "fail", "hang"
    if oc == "success" and not m["complete"] and ideal == "success":
        return "fail", "truncated answer presented as success"
    failed_required = [c["id"] for c in checks if c["status"] == "fail" and c["severity"] != "advisory"]
    if failed_required:
        return "fail", "failed: " + ", ".join(failed_required)
    failed_advisory = [c["id"] for c in checks if c["status"] == "fail" and c["severity"] == "advisory"]
    if ideal == "success":
        rescued = oc == "success" and m["complete"]
    else:
        rescued = oc == "error"
        if oc == "success":
            return "partial", "answered by routing around the rejection"
    if rescued:
        if failed_advisory:
            return "partial", "rescued; advisory: " + ", ".join(failed_advisory)
        return "pass", "rescued"
    return "safe", f"not rescued — clean error: {str(m.get('error'))[:80]}"


# --------------------------------------------------------------------- running
async def guarded_call(adapter, primary, fallback, stream, messages, max_wall_s) -> CallResult:
    t0 = time.monotonic()
    try:
        r = await asyncio.wait_for(adapter.complete(primary, fallback, stream, messages, max_wall_s), timeout=max_wall_s + 1.0)
    except asyncio.TimeoutError:
        r = CallResult(ok=False, hang=True, error=f"hang: no result within {max_wall_s:g}s", elapsed_s=round(time.monotonic() - t0, 3))
    except Exception as exc:  # an adapter crash is a finding, not a runner failure
        r = CallResult(ok=False, error=f"adapter crashed: {type(exc).__name__}: {str(exc)[:300]}", elapsed_s=round(time.monotonic() - t0, 3))
    if not r.elapsed_s:
        r.elapsed_s = round(time.monotonic() - t0, 3)
    return r


def base_metrics(sc: dict, fallback_model: str, r: CallResult, log_entries: list[dict]) -> dict:
    prim = [e for e in log_entries if tagkey(e.get("model")) == tagkey(sc["model"])]
    fb = [e for e in log_entries if tagkey(e.get("model")) == tagkey(fallback_model)]
    return {
        "outcome": "hang" if r.hang else ("success" if r.ok else "error"),
        "complete": norm(r.content) == CANON,
        "content": r.content,
        "error": r.error,
        "status": r.status,
        "elapsed_s": r.elapsed_s,
        "ttft_s": r.ttft_s,
        "reported_model": r.reported_model,
        "usage": r.usage,
        "fallback_model": fallback_model,
        "attempts_primary": len(prim),
        "attempts_fallback": len(fb),
        "primary_times": [e["t"] for e in prim],
        "fallback_times": [e["t"] for e in fb],
        "first_gap_s": round(prim[1]["t"] - prim[0]["t"], 3) if len(prim) >= 2 else None,
        "prefill_rejections": sum(1 for e in log_entries if str(e.get("action", "")).startswith("400 prefill")),
        "wall_actions": [f"{e['t']:.2f}s {tagkey(e.get('model'))} #{e.get('attempt')} -> {e.get('action')}" for e in log_entries],
    }


async def alive_probe(adapter, messages) -> tuple[bool, str | None]:
    r = await guarded_call(adapter, "fb-ok", None, False, messages, 10.0)
    ok = r.ok and norm(r.content) == CANON
    return ok, (None if ok else (r.error or "answer was not the canonical text"))


async def run_scenario(adapter, caps, wall: WallControl, sc: dict, cat: dict, profile: str, timing: dict) -> dict:
    messages = [{"role": "user", "content": cat["prompt"]}]
    fallback_model = sc.get("fallback_model", cat.get("default_fallback", "fb-ok"))
    fallback_arg = fallback_model if caps.get("fallback") else None
    stream = bool(sc.get("stream", True))
    max_wall = float(sc.get("max_wall_s", cat.get("default_max_wall_s", 45)))
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    await wall.reset()
    if sc.get("mode") == "sequence":
        seq = sc.get("fast_sequence") if profile == "fast" and sc.get("fast_sequence") else sc["sequence"]
        t_reset = time.monotonic()
        items = []
        for i in range(int(seq["count"])):
            target = t_reset + i * float(seq["interval_s"])
            now = time.monotonic()
            if target > now:
                await asyncio.sleep(target - now)
            t_sent = round(time.monotonic() - t_reset, 3)
            r = await guarded_call(adapter, sc["model"], fallback_arg, stream, messages, float(seq["per_request_max_wall_s"]))
            items.append({"i": i, "t_sent": t_sent, "outcome": "hang" if r.hang else ("success" if r.ok else "error"),
                          "complete": norm(r.content) == CANON, "elapsed_s": r.elapsed_s,
                          "reported_model": r.reported_model, "error": r.error})
        last = r
        logd = await wall.log()
        entries = logd["log"]
        down = float(logd["timing"]["flap_down_s"])
        m = base_metrics(sc, fallback_model, last, entries)
        prim = [e for e in entries if tagkey(e.get("model")) == tagkey(sc["model"])]
        recovered = [e["t"] for e in prim if str(e.get("action", "")).startswith("200")]
        during = [it for it in items if it["t_sent"] < down]
        m.update({
            "outcome": "hang" if any(it["outcome"] == "hang" for it in items) else
                       ("success" if all(it["outcome"] == "success" for it in items) else "error"),
            "complete": all(it["complete"] for it in items),
            "error": next((it["error"] for it in items if it["outcome"] != "success"), None),
            "elapsed_s": round(time.monotonic() - t_reset, 3),
            "seq_items": items,
            "seq_hangs": sum(1 for it in items if it["outcome"] == "hang"),
            "seq_requests_during_down": len(during),
            "seq_served_during_down": sum(1 for it in during if it["outcome"] == "success"),
            "seq_primary_attempts_during_down": sum(1 for e in prim if e["t"] < down),
            "seq_recovered_after_s": round(min(recovered) - down, 3) if recovered else None,
            "seq_success_after_down": sum(1 for it in items if it["t_sent"] >= down and it["outcome"] == "success"),
            "flap_down_s": down,
        })
    else:
        r = await guarded_call(adapter, sc["model"], fallback_arg, stream, messages, max_wall)
        logd = await wall.log()
        m = base_metrics(sc, fallback_model, r, logd["log"])

    alive, alive_err = await alive_probe(adapter, messages)
    m["alive_after"], m["alive_error"] = alive, alive_err

    checks = [evaluate_check(c, m, caps, profile) for c in (sc.get("checks") or [])]
    verdict, reason = verdict_for(sc, checks, m)
    return {"id": sc["id"], "title": sc["title"], "model": sc["model"], "fallback_model": fallback_model,
            "ideal": sc.get("ideal", "success"), "stream": stream, "mode": sc.get("mode", "single"),
            "started_at": started, "verdict": verdict, "reason": reason,
            "checks": checks, "metrics": {k: v for k, v in m.items() if k != "content"},
            "content_ok": m["complete"]}


async def run_system(system_path: str, catalogue_path: str, wall_base: str, profile: str, only: set[str] | None,
                     out_dir: str, quiet: bool = False) -> str:
    system = load_yaml(system_path)
    cat = load_yaml(catalogue_path)
    wall = WallControl(wall_base)
    try:
        health = await wall.health()
    except Exception as exc:
        raise SystemExit(f"cannot reach the wall at {wall_base}: {exc}\nstart it with: python -m failoverbench wall --profile {profile}")
    timing = await wall.config(profile)
    adapter = make_adapter(system["adapter"], system.get("params") or {}, wall_base)
    caps = {**adapter.capabilities, **(system.get("capabilities") or {})}
    await adapter.start()
    results = []
    t_run = time.monotonic()
    try:
        for sc in cat["scenarios"]:
            if only and sc["id"] not in only:
                continue
            res = await run_scenario(adapter, caps, wall, sc, cat, profile, timing)
            results.append(res)
            if not quiet:
                mark = {"pass": "PASS", "fail": "FAIL", "partial": "PART", "safe": "SAFE", "na": " n/a"}[res["verdict"]]
                mm = res["metrics"]
                print(f"  {res['id']} {mark}  {res['title']:<36} outcome={mm['outcome']:<7} "
                      f"attempts p/f={mm['attempts_primary']}/{mm['attempts_fallback']} wall={mm['elapsed_s']:.1f}s", flush=True)
    finally:
        await adapter.close()
        await wall.close()
    doc = {
        "failoverbench": __version__,
        "methodology": cat.get("version"),
        "profile": profile,
        "timing": timing,
        "wall": health,
        "system": {"name": system["name"], "label": system.get("label", system["name"]), **adapter.describe(),
                   "capabilities": caps, "notes": system.get("notes")},
        "run_started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_seconds": round(time.monotonic() - t_run, 1),
        "summary": {v: sum(1 for r in results if r["verdict"] == v) for v in ("pass", "partial", "safe", "fail", "na")},
        "scenarios": results,
    }
    os.makedirs(os.path.join(out_dir, profile), exist_ok=True)
    out_path = os.path.join(out_dir, profile, f"{system['name']}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return out_path


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="failoverbench run", description="Run one system under test through the catalogue.")
    ap.add_argument("--system", required=True, help="systems/<name>.yaml")
    ap.add_argument("--catalogue", default="scenarios/catalogue.yaml")
    ap.add_argument("--wall", default="http://127.0.0.1:8401", help="the wall's base URL (control endpoints live here)")
    ap.add_argument("--profile", choices=("fast", "full"), default="full")
    ap.add_argument("--only", default="", help="comma-separated scenario ids, e.g. S01,S08")
    ap.add_argument("--out", default="results")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    only = {s.strip().upper() for s in args.only.split(",") if s.strip()} or None
    path = asyncio.run(run_system(args.system, args.catalogue, args.wall, args.profile, only, args.out, args.quiet))
    print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
