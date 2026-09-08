"""Render the scorecard (Markdown) from the JSON results of one profile."""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys

import yaml

MARK = {"pass": "✅", "partial": "◐", "safe": "○", "fail": "❌", "na": "—"}
WORD = {"pass": "pass", "partial": "partial", "safe": "safe", "fail": "fail", "na": "n/a"}


def run_date_local(docs: list[dict]) -> str:
    """The date of the latest run start, in the machine's local timezone (runs are
    stamped in UTC; a 22:00 UTC run on the 6th is the 7th in IST, and the
    scorecard is dated where it was run)."""
    stamps = [d.get("run_started_at") for d in docs if d.get("run_started_at")]
    if not stamps:
        return dt.date.today().isoformat()
    latest = max(stamps)
    try:
        return dt.datetime.fromisoformat(latest).astimezone().date().isoformat()
    except ValueError:
        return latest[:10]


def key_detail(res: dict) -> str:
    m = res["metrics"]
    bits = []
    if m.get("outcome") == "hang":
        bits.append("HANG")
    if res.get("mode") == "sequence":
        bits.append(f"{m.get('seq_served_during_down', 0)}/{m.get('seq_requests_during_down', 0)} served in outage")
        rec = m.get("seq_recovered_after_s")
        bits.append("back on primary " + (f"{rec:+.0f}s" if rec is not None else "never"))
    else:
        bits.append(f"{m['attempts_primary']}p/{m['attempts_fallback']}f")
        if m.get("first_gap_s") is not None:
            bits.append(f"gap {m['first_gap_s']:.1f}s")
        bits.append(f"{m['elapsed_s']:.1f}s")
        if m["outcome"] == "success" and not res.get("content_ok"):
            bits.append("TRUNCATED")
    return " · ".join(bits)


def render(results_dir: str, profile: str, catalogue_path: str | None = None) -> str:
    docs = []
    for path in sorted(glob.glob(os.path.join(results_dir, profile, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            docs.append(json.load(fh))
    if not docs:
        raise SystemExit(f"no results in {results_dir}/{profile}")
    cat = None
    if catalogue_path and os.path.exists(catalogue_path):
        with open(catalogue_path, encoding="utf-8") as fh:
            cat = yaml.safe_load(fh)
    scen_meta = {s["id"]: s for s in (cat or {}).get("scenarios", [])}
    ids: list[str] = []
    for d in docs:
        for r in d["scenarios"]:
            if r["id"] not in ids:
                ids.append(r["id"])
    by = {d["system"]["name"]: {r["id"]: r for r in d["scenarios"]} for d in docs}
    # Rows that cover only part of the catalogue are contrast rows (e.g. one
    # scenario re-run under a different setting); they get their own table.
    full_docs = [d for d in docs if len(d["scenarios"]) == len(ids)]
    contrast_docs = [d for d in docs if len(d["scenarios"]) != len(ids)]
    docs = full_docs or docs

    run_date = run_date_local(docs)
    lines = [f"# Failover Bench scorecard — {run_date}", ""]
    lines.append(f"Profile **{profile}** · methodology v{docs[0].get('methodology')} · failoverbench {docs[0]['failoverbench']} · "
                 f"{len(docs)} system(s) · {len(ids)} scenario(s)")
    lines.append("")
    lines.append("Every cell is one scenario run through one system against the same misbehaving provider. "
                 "**pass** = the caller got the complete answer and the system behaved; **partial** = rescued, with an advisory conduct issue; "
                 "**safe** = not rescued, but a bounded, clean error; **fail** = a hang, a truncated answer presented as success, or a conduct check failed. "
                 "`Np/Mf` = attempts the provider saw on the primary / fallback model; `gap` = seconds between the first two primary attempts.")
    lines.append("")
    header = "| Scenario | " + " | ".join(d["system"]["label"] for d in docs) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(docs))
    for sid in ids:
        meta = scen_meta.get(sid, {})
        title = meta.get("title") or next((by[n][sid]["title"] for n in by if sid in by[n]), sid)
        row = [f"**{sid}** {title}"]
        for d in docs:
            r = by[d["system"]["name"]].get(sid)
            if not r:
                row.append("—")
                continue
            row.append(f"{MARK[r['verdict']]} {WORD[r['verdict']]}<br><sub>{key_detail(r)}</sub>")
        lines.append("| " + " | ".join(row) + " |")
    if contrast_docs and full_docs:
        lines.append("")
        lines.append("Contrast rows (a subset of scenarios re-run under a different setting):")
        lines.append("")
        for d in contrast_docs:
            cells = "; ".join(f"{r['id']} {MARK[r['verdict']]} {WORD[r['verdict']]} ({key_detail(r)})" for r in d["scenarios"])
            lines.append(f"- **{d['system']['label']}** — {cells}")
    docs = full_docs + contrast_docs if full_docs else docs
    lines.append("")
    lines.append("| System | pass | partial | safe | fail | run time |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for d in docs:
        s = d["summary"]
        lines.append(f"| {d['system']['label']} | {s['pass']} | {s['partial']} | {s.get('safe', 0)} | {s['fail']} | {d['run_seconds']:.0f}s |")
    lines.append("")
    lines.append("## Check-level detail")
    for d in docs:
        sysd = d["system"]
        lines.append("")
        lines.append(f"### {sysd['label']}")
        caps = ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in sysd["capabilities"].items())
        lines.append(f"adapter `{sysd['adapter']}` · capabilities: {caps} · params: `{json.dumps(sysd.get('params') or {})}`")
        if sysd.get("notes"):
            lines.append("")
            lines.append(sysd["notes"])
        for r in d["scenarios"]:
            lines.append("")
            lines.append(f"**{r['id']} {r['title']}** — {MARK[r['verdict']]} {WORD[r['verdict']]} — {r.get('reason', '')}")
            for c in r["checks"]:
                tag = {"pass": "pass", "fail": "FAIL", "na": "n/a", "info": "info"}[c["status"]]
                sev = " (advisory)" if c["severity"] == "advisory" and c["status"] == "fail" else ""
                lines.append(f"- `{c['id']}` {tag}{sev}: {c['detail']}")
            acts = r["metrics"].get("wall_actions") or []
            if acts:
                shown = acts[:12]
                more = f" … (+{len(acts) - 12} more)" if len(acts) > 12 else ""
                lines.append(f"- wall log: {'; '.join(shown)}{more}")
    lines.append("")
    lines.append("---")
    lines.append("Results are published under CC BY 4.0; the harness is MIT. Methodology and raw logs: see the repository.")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="failoverbench report", description="Render SCORECARD.md from results.")
    ap.add_argument("--results", default="results")
    ap.add_argument("--profile", choices=("fast", "full"), default="full")
    ap.add_argument("--catalogue", default="scenarios/catalogue.yaml")
    ap.add_argument("--out", default=None, help="output path (default: results/<profile>/SCORECARD.md)")
    args = ap.parse_args(argv)
    text = render(args.results, args.profile, args.catalogue)
    out = args.out or os.path.join(args.results, args.profile, "SCORECARD.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
