"""Render the public scorecard page (docs/index.html) from results/<profile>.

Self-contained HTML: inline CSS, no scripts, light and dark themes. Publish
with GitHub Pages from the docs/ folder.
"""

from __future__ import annotations

import datetime as dt
import glob
import html
import json
import os
import sys

import yaml

from .report import key_detail, run_date_local

WORD = {"pass": "pass", "partial": "partial", "safe": "safe", "fail": "fail", "na": "n/a"}

CSS = """
:root{--bg:#F4F6F8;--surface:#fff;--ink:#1B2128;--ink2:#4A5563;--ink3:#7B8794;--line:#D5DCE3;--accent:#D98A00;--accent-ink:#8A5700;
--pass:#DDF3E4;--pass-ink:#1E6B3F;--partial:#FFF0CC;--partial-ink:#7A5200;--safe:#E6EBF1;--safe-ink:#3E4A58;--fail:#FBDDDD;--fail-ink:#8F1F1F;--na:#F1F3F5;--na-ink:#7B8794}
@media (prefers-color-scheme:dark){:root{--bg:#121619;--surface:#1A2026;--ink:#E8ECF0;--ink2:#B3BCC6;--ink3:#7F8A96;--line:#2B343D;--accent:#F2A93B;--accent-ink:#F2A93B;
--pass:#153B26;--pass-ink:#8FD9AA;--partial:#3B2E0C;--partial-ink:#F2C86B;--safe:#232B34;--safe-ink:#B3BCC6;--fail:#3F1717;--fail-ink:#F19A9A;--na:#1E252C;--na-ink:#7F8A96}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "IBM Plex Sans","Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.hazard{height:8px;background:repeating-linear-gradient(135deg,var(--accent) 0 14px,#1B2128 14px 28px)}
.page{max-width:1100px;margin:0 auto;padding:32px 20px 80px}
h1{font-family:"Barlow Condensed","Arial Narrow",Arial,sans-serif;font-size:56px;line-height:1;margin:0 0 6px;font-weight:700}
h2{font-family:"Barlow Condensed","Arial Narrow",Arial,sans-serif;font-size:30px;margin:40px 0 10px;font-weight:600}
.eyebrow{font-family:"IBM Plex Mono",Menlo,Consolas,monospace;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin-bottom:8px}
p{max-width:70ch}.lede{font-size:19px;max-width:62ch;color:var(--ink)}.muted{color:var(--ink2)}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px}.legend span{padding:4px 10px;border-radius:3px;font-size:14px}
.wrap{overflow-x:auto;border:1px solid var(--line);background:var(--surface);margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{font-family:"IBM Plex Mono",Menlo,Consolas,monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);font-weight:500;background:var(--bg)}
tr:last-child td{border-bottom:0}td.sc{white-space:nowrap;font-weight:600}td.sc small{display:block;font-weight:400;color:var(--ink2);white-space:normal}
td.cell{min-width:150px}.v{display:inline-block;padding:2px 8px;border-radius:3px;font-weight:600;font-size:13px}
.v.pass{background:var(--pass);color:var(--pass-ink)}.v.partial{background:var(--partial);color:var(--partial-ink)}
.v.safe{background:var(--safe);color:var(--safe-ink)}.v.fail{background:var(--fail);color:var(--fail-ink)}.v.na{background:var(--na);color:var(--na-ink)}
td.cell sub{display:block;font-size:12px;color:var(--ink2);margin-top:4px;vertical-align:baseline}
.sum td:nth-child(n+2){text-align:right;font-variant-numeric:tabular-nums}
details{border:1px solid var(--line);background:var(--surface);padding:10px 14px;margin:8px 0}summary{cursor:pointer;font-weight:600}
details ul{margin:6px 0 10px;padding-left:18px;font-size:14px}details li{margin:2px 0}code{font-family:"IBM Plex Mono",Menlo,Consolas,monospace;font-size:.9em}
a{color:var(--accent-ink)}footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--ink3)}
"""


def render_site(results_dir: str, profile: str, catalogue_path: str, repo_url: str, next_scorecard: str,
                site_url: str = "https://failoverbench.github.io/failoverbench") -> str:
    docs = []
    for path in sorted(glob.glob(os.path.join(results_dir, profile, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            docs.append(json.load(fh))
    if not docs:
        raise SystemExit(f"no results in {results_dir}/{profile}")
    cat = {}
    if catalogue_path and os.path.exists(catalogue_path):
        with open(catalogue_path, encoding="utf-8") as fh:
            cat = yaml.safe_load(fh)
    meta = {s["id"]: s for s in cat.get("scenarios", [])}
    ids: list[str] = []
    for d in docs:
        for r in d["scenarios"]:
            if r["id"] not in ids:
                ids.append(r["id"])
    by = {d["system"]["name"]: {r["id"]: r for r in d["scenarios"]} for d in docs}
    full_docs = [d for d in docs if len(d["scenarios"]) == len(ids)]
    contrast_docs = [d for d in docs if len(d["scenarios"]) != len(ids)]
    all_docs = docs
    docs = full_docs or docs
    run_date = run_date_local(all_docs)
    esc = html.escape

    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Failover Bench — scorecard {esc(run_date)}</title>",
           f"<meta property='og:title' content='Failover Bench — scorecard {esc(run_date)}'>",
           "<meta property='og:description' content='How LLM gateways and SDKs behave when the provider behind them misbehaves: sixteen documented faults, one fake provider, every result reproducible with one command.'>",
           f"<meta property='og:image' content='{esc(site_url.rstrip('/'))}/scorecard.png'>",
           "<meta name='twitter:card' content='summary_large_image'>",
           "<link rel='preconnect' href='https://fonts.googleapis.com'>",
           "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap'>",
           f"<style>{CSS}</style></head><body><div class='hazard'></div><div class='page'>",
           f"<div class='eyebrow'>Scorecard · {esc(run_date)} · profile {esc(profile)} · methodology v{esc(str(docs[0].get('methodology')))} · failoverbench {esc(docs[0]['failoverbench'])}</div>",
           "<h1>Failover Bench</h1>",
           "<p class='lede'>A crash-test lab for LLM gateways and SDKs. One fake provider breaks on purpose in sixteen documented ways; every system below is pushed through the same sixteen faults; each cell is what the caller actually got.</p>",
           f"<p class='muted'>Next scorecard: <strong>{esc(next_scorecard)}</strong>. Harness, methodology and raw logs: <a href='{esc(repo_url)}'>{esc(repo_url.replace('https://', ''))}</a>.</p>",
           "<div class='legend'><span class='v pass'>pass</span><span>caller got the complete answer, conduct clean</span>"
           "<span class='v partial'>partial</span><span>rescued, advisory check failed</span>"
           "<span class='v safe'>safe</span><span>not rescued, but a bounded clean error</span>"
           "<span class='v fail'>fail</span><span>hang, truncated answer as success, or a conduct check failed</span></div>",
           "<div class='wrap'><table><thead><tr><th>Scenario</th>"]
    out += [f"<th>{esc(d['system']['label'])}</th>" for d in docs]
    out.append("</tr></thead><tbody>")
    for sid in ids:
        m = meta.get(sid, {})
        title = m.get("title") or next((by[n][sid]["title"] for n in by if sid in by[n]), sid)
        fault = m.get("fault", "")
        out.append(f"<tr><td class='sc'>{esc(sid)} {esc(title)}<small>{esc(fault)}</small></td>")
        for d in docs:
            r = by[d["system"]["name"]].get(sid)
            if not r:
                out.append("<td class='cell'><span class='v na'>—</span></td>")
                continue
            v = r["verdict"]
            out.append(f"<td class='cell'><span class='v {v}'>{WORD[v]}</span><sub>{esc(key_detail(r))}</sub></td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")

    if contrast_docs and full_docs:
        out.append("<h2>Contrast rows</h2><p class='muted'>A subset of scenarios re-run under a different setting, shown next to the row they contrast with.</p>")
        for d in contrast_docs:
            cells = "; ".join(f"{esc(r['id'])} <span class='v {r['verdict']}'>{WORD[r['verdict']]}</span> {esc(key_detail(r))}" for r in d["scenarios"])
            out.append(f"<p><strong>{esc(d['system']['label'])}</strong> — {cells}</p>")
    out.append("<div class='wrap'><table class='sum'><thead><tr><th>System</th><th>pass</th><th>partial</th><th>safe</th><th>fail</th><th>run</th></tr></thead><tbody>")
    for d in all_docs:
        s = d["summary"]
        out.append(f"<tr><td>{esc(d['system']['label'])}</td><td>{s['pass']}</td><td>{s['partial']}</td><td>{s.get('safe', 0)}</td><td>{s['fail']}</td><td>{d['run_seconds']:.0f}s</td></tr>")
    out.append("</tbody></table></div>")

    out.append("<h2>Check-level detail</h2><p class='muted'>Every check the runner scored, and what the fake provider saw. Advisory checks change a pass to partial; required checks change it to fail.</p>")
    for d in all_docs:
        sysd = d["system"]
        caps = ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in sysd["capabilities"].items())
        out.append(f"<details><summary>{esc(sysd['label'])} — adapter <code>{esc(sysd['adapter'])}</code>, {esc(caps)}</summary>")
        if sysd.get("notes"):
            out.append(f"<p class='muted'>{esc(sysd['notes'])}</p>")
        out.append(f"<p class='muted'>params: <code>{esc(json.dumps(sysd.get('params') or {}))}</code></p>")
        for r in d["scenarios"]:
            out.append(f"<p><strong>{esc(r['id'])} {esc(r['title'])}</strong> — <span class='v {r['verdict']}'>{WORD[r['verdict']]}</span> {esc(r.get('reason', ''))}</p><ul>")
            for c in r["checks"]:
                tag = {"pass": "pass", "fail": "FAIL", "na": "n/a", "info": "info"}[c["status"]]
                sev = " (advisory)" if c["severity"] == "advisory" and c["status"] == "fail" else ""
                out.append(f"<li><code>{esc(c['id'])}</code> {tag}{esc(sev)}: {esc(c['detail'])}</li>")
            acts = r["metrics"].get("wall_actions") or []
            if acts:
                shown = "; ".join(acts[:12]) + (f" … (+{len(acts) - 12} more)" if len(acts) > 12 else "")
                out.append(f"<li>wall log: {esc(shown)}</li>")
            out.append("</ul>")
        out.append("</details>")
    out.append(f"<footer>Results CC BY 4.0 · harness MIT · generated {esc(dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))} from results/{esc(profile)} · <a href='{esc(repo_url)}/blob/main/METHODOLOGY.md'>methodology</a> · <a href='{esc(repo_url)}/tree/main/results/{esc(profile)}'>raw results</a></footer>")
    out.append("</div></body></html>")
    return "\n".join(out) + "\n"


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="failoverbench site", description="Render docs/index.html from results.")
    ap.add_argument("--results", default="results")
    ap.add_argument("--profile", choices=("fast", "full"), default="full")
    ap.add_argument("--catalogue", default="scenarios/catalogue.yaml")
    ap.add_argument("--repo-url", default="https://github.com/failoverbench/failoverbench")
    ap.add_argument("--next", default="Monday 5 October 2026", help="text for the next-scorecard line")
    ap.add_argument("--site-url", default="https://failoverbench.github.io/failoverbench", help="where docs/ is served (for link previews)")
    ap.add_argument("--out", default="docs/index.html")
    ap.add_argument("--no-images", action="store_true", help="skip the PNGs (scorecard.png, how-it-works.png)")
    args = ap.parse_args(argv)
    text = render_site(args.results, args.profile, args.catalogue, args.repo_url, args.next, args.site_url)
    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {args.out}", file=sys.stderr)
    if not args.no_images:
        try:
            from .charts import explainer_png, scorecard_png
        except ImportError:
            print("images skipped: pip install -e '.[charts]' for docs/scorecard.png and docs/how-it-works.png", file=sys.stderr)
            return
        scorecard_png(args.results, args.profile, args.catalogue, os.path.join(out_dir, "scorecard.png"))
        explainer_png(os.path.join(out_dir, "how-it-works.png"))
        print(f"wrote {out_dir}/scorecard.png and {out_dir}/how-it-works.png", file=sys.stderr)


if __name__ == "__main__":
    main()
