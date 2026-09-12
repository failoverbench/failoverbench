"""Shareable images from results/<profile>: the scorecard grid and a per-scenario
timeline card. Plain matplotlib, no seaborn, one hue per job.

    python -m failoverbench chart scorecard [--profile full] [--out docs/scorecard.png]
    python -m failoverbench chart timeline --scenario S06 results/full/bifrost.json [notices/other.json] [--out …]

Palette: status colours carry meaning only together with a glyph and a word;
large fills are tints, saturated colour is reserved for small marks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path  # noqa: E402

from .runner import load_yaml  # noqa: E402

INK = {"primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7"}
SURFACE = "#fcfcfb"
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
VERDICT = {  # verdict -> (glyph, fill tint, chip colour, word, meaning)
    "pass": ("✓", "#d3edd3", STATUS["good"], "pass", "complete answer, every check clean"),
    "partial": ("◐", "#feefc8", STATUS["warning"], "partial", "answered, but an advisory check failed"),
    "safe": ("–", "#ebeae5", INK["axis"], "safe", "no answer, but a clean, bounded error"),
    "fail": ("✕", "#f6d3d3", STATUS["critical"], "fail", "a hang, a truncated answer shown as success, or a required check failed"),
    "na": ("", SURFACE, SURFACE, "n/a", "not applicable"),
}
FONT = {"family": "DejaVu Sans"}


def _mix(hex_colour: str, alpha: float, base: str = SURFACE) -> str:
    """Tint: hex_colour at `alpha` over the surface."""
    h = lambda s: tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
    c, b = h(hex_colour), h(base)
    return "#%02x%02x%02x" % tuple(round(a * alpha + bb * (1 - alpha)) for a, bb in zip(c, b))


def _measure(fig, text: str, fontsize: float, weight: str = "normal") -> float:
    """Rendered width of `text` in pixels (figure at dpi 100)."""
    t = fig.text(0, 0, text, fontsize=fontsize, fontweight=weight, **FONT)
    w = t.get_window_extent(renderer=fig.canvas.get_renderer()).width
    t.remove()
    return w


def _sentence_with(text: str, needle: str) -> str | None:
    for sent in re.split(r"(?<=[^\d])\.\s+", text or ""):
        if needle in sent:
            return sent.strip().rstrip(".") + "."
    return None


def _wrap(fig, text: str, fontsize: float, max_px: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and _measure(fig, trial, fontsize) > max_px:
            lines.append(cur); cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _round_right_bar(ax, x0, x1, y, h, colour, r):
    """A horizontal bar square at its start and rounded (radius r, data units) at its data end."""
    if x1 - x0 <= 2 * r:
        ax.add_patch(Rectangle((x0, y - h / 2), x1 - x0, h, facecolor=colour, edgecolor="none"))
        return
    y0, y1 = y - h / 2, y + h / 2
    verts = [(x0, y0), (x1 - r, y0), (x1, y0), (x1, y0 + r), (x1, y1 - r), (x1, y1), (x1 - r, y1), (x0, y1), (x0, y0)]
    codes = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=colour, edgecolor="none"))


# ------------------------------------------------------------------ scorecard

SHORT = [  # (regex on system name, two-line column header)
    (r"^reference$", "Reference\nclient"),
    (r"^direct$", "No\ngateway\n(control)"),
    (r"^bifrost$", "Bifrost"),
    (r"^dsh$", "DeepSeek\nHarness +\nplugin"),
    (r"^langchain$", "LangChain\nfallbacks"),
    (r"^litellm-proxy$", "LiteLLM\nproxy"),
    (r"^litellm-router$", "LiteLLM\nRouter"),
    (r"^litellm-router-tuned$", "LiteLLM\nRouter\ntuned"),
    (r"^openai-python$", "openai-\npython\nSDK"),
    (r"^portkey-gateway$", "Portkey\nGateway"),
]


def _short(name: str, label: str) -> str:
    for pat, s in SHORT:
        if re.match(pat, name):
            return s
    return label[:18]


def _version_tag(label: str) -> str:
    m = re.search(r"\bv?\d+\.\d+(\.\d+)?", label)
    return m.group(0) if m else ""


def scorecard_png(results_dir: str, profile: str, catalogue_path: str, out: str, date_text: str | None = None,
                  edition: str = "") -> str:
    cat = load_yaml(catalogue_path)
    ids = [s["id"] for s in cat["scenarios"]]
    titles = {s["id"]: s["title"] for s in cat["scenarios"]}
    docs = []
    for fn in sorted(os.listdir(os.path.join(results_dir, profile))):
        if fn.endswith(".json"):
            with open(os.path.join(results_dir, profile, fn), encoding="utf-8") as fh:
                docs.append(json.load(fh))
    full = [d for d in docs if len(d["scenarios"]) == len(ids)]
    contrast = [d for d in docs if len(d["scenarios"]) != len(ids)]
    order = {"reference": 0, "direct": 2}
    full.sort(key=lambda d: (order.get(d["system"]["name"], 1), d["system"]["name"]))
    by = {d["system"]["name"]: {r["id"]: r for r in d["scenarios"]} for d in full}
    names = [d["system"]["name"] for d in full]
    if date_text is None:
        newest = max(d.get("run_started_at", "") for d in docs)
        date_text = newest[:10]

    # footnotes are wrapped first so the canvas height can fit them
    notes = []
    for d in contrast:
        r = d["scenarios"][0]
        notes.append(f"Contrast row, not scored: {d['system']['label']} — {r['id']} {VERDICT[r['verdict']][3]}.")
    for d in full:
        sent = _sentence_with(d["system"].get("notes") or "", "not scored here")
        if sent:
            notes.append(f"{_short(d['system']['name'], d['system']['label']).replace(chr(10), ' ')}: {sent}")
    W = 1200
    probe = plt.figure(figsize=(W / 100, 1), dpi=100)
    note_lines = [_wrap(probe, n, 11.5, W - 120) for n in notes[:3]]
    plt.close(probe)
    n_lines = sum(len(x) for x in note_lines)
    notes_start = 268 + len(ids) * 54 + 18 + 70 + 34 + 4 * 30 + 24   # header + grid + totals + legend
    H = notes_start + 20 * n_lines + 6 * len(note_lines) + 70
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    T = lambda x, y, s, **k: ax.text(x, y, s, **{**FONT, **k})  # noqa: E731

    # header
    T(60, 78, "Failover Bench scorecard" + (f" — {edition}" if edition else ""), fontsize=30, fontweight="semibold", color=INK["primary"], va="center")
    T(60, 122, f"{len(ids)} ways a provider can break × {len(full)} gateways and SDKs — one fake provider, one baseline setup",
      fontsize=14, color=INK["secondary"], va="center")
    T(60, 148, f"2 retries · 30 s timeout · one fallback · methodology v{cat.get('version')} · results as of {date_text} · "
      f"one-command repro and raw log for every cell", fontsize=12.5, color=INK["muted"], va="center")

    # grid geometry
    left, top = 356, 268
    ncol, nrow = len(names), len(ids)
    cw, ch, gap = (W - left - 60) / ncol, 54, 2
    # column headers (up to three short lines, bottom-aligned to the grid)
    for j, n in enumerate(names):
        cx = left + j * cw + cw / 2
        T(cx, top - 14, _short(n, full[j]["system"]["label"]), fontsize=11, color=INK["primary"], ha="center", va="bottom", linespacing=1.15)
    # rows
    for i, sid in enumerate(ids):
        y = top + i * ch
        T(left - 16, y + ch / 2, f"{sid}  {titles[sid]}", fontsize=12, color=INK["primary"], ha="right", va="center")
        for j, n in enumerate(names):
            r = by[n].get(sid)
            v = r["verdict"] if r else "na"
            glyph, tint, chip, word, _ = VERDICT[v]
            x = left + j * cw
            ax.add_patch(Rectangle((x + gap / 2, y + gap / 2), cw - gap, ch - gap, facecolor=tint, edgecolor="none"))
            if glyph:
                T(x + cw / 2, y + ch / 2 + 1, glyph, fontsize=17, color=INK["primary"], ha="center", va="center", fontweight="bold")
    # totals row
    ty = top + nrow * ch + 18
    ax.plot([left, W - 60], [ty - 8, ty - 8], color=INK["axis"], linewidth=1)
    T(left - 16, ty + 16, "pass · partial · safe · fail", fontsize=11, color=INK["muted"], ha="right", va="center")
    for j, n in enumerate(names):
        sm = full[j]["summary"]
        T(left + j * cw + cw / 2, ty + 16, f"{sm['pass']}·{sm['partial']}·{sm['safe']}·{sm['fail']}", fontsize=11,
          color=INK["secondary"], ha="center", va="center")

    # legend
    ly = ty + 70
    T(60, ly, "How to read a cell", fontsize=13, fontweight="semibold", color=INK["primary"], va="center")
    for k, v in enumerate(["pass", "partial", "safe", "fail"]):
        glyph, tint, chip, word, meaning = VERDICT[v]
        yy = ly + 34 + k * 30
        ax.add_patch(Rectangle((60, yy - 11), 34, 22, facecolor=tint, edgecolor="none"))
        T(77, yy + 1, glyph, fontsize=13, color=INK["primary"], ha="center", va="center", fontweight="bold")
        T(108, yy, word, fontsize=13, fontweight="semibold", color=INK["primary"], va="center")
        T(190, yy, meaning, fontsize=13, color=INK["secondary"], va="center")

    # footnotes
    yy = ly + 34 + 4 * 30 + 24
    for lines in note_lines:
        for ln in lines:
            T(60, yy, ln, fontsize=11.5, color=INK["muted"], va="center")
            yy += 20
        yy += 6
    T(60, H - 46, "Rows score the newest installable version. Harness MIT · results CC BY 4.0 · github.com/failoverbench/failoverbench",
      fontsize=12, color=INK["secondary"], va="center")
    fig.savefig(out, dpi=100, facecolor=SURFACE)
    plt.close(fig)
    return out


# ------------------------------------------------------------------- timeline

_ACTION = re.compile(r"^(?P<t>[\d.]+)s\s+(?P<model>\S+)\s+#(?P<n>\d+)\s+->\s+(?P<action>.*)$")


def _segments(res: dict, timing_hold_s: float = 120.0) -> list[dict]:
    """Turn a scenario result's wall log into timeline bars from the client's point of view."""
    m = res["metrics"]
    end = float(m["elapsed_s"])
    fb = res.get("fallback_model", "")
    acts = []
    for line in m.get("wall_actions") or []:
        mm = _ACTION.match(line)
        if mm:
            acts.append({"t": float(mm["t"]), "model": mm["model"], "n": int(mm["n"]), "action": mm["action"]})
    segs = []
    for k, a in enumerate(acts):
        nxt = acts[k + 1]["t"] if k + 1 < len(acts) else end
        is_fb = a["model"] == fb
        if "no-response" in a["action"]:
            stop = min(nxt, a["t"] + timing_hold_s, end)
            cut_by_client = stop == end and k + 1 == len(acts) and nxt == end and end < a["t"] + timing_hold_s
            segs.append({"x0": a["t"], "x1": stop, "kind": "wait",
                         "label": f"attempt {a['n']} · still silent" if cut_by_client else f"attempt {a['n']} · silent for {stop - a['t']:.0f} s"})
        elif a["action"].startswith("200"):
            segs.append({"x0": a["t"], "x1": max(nxt, a["t"] + 0.6), "kind": "answer" if is_fb else "answer",
                         "label": ("fallback answered" if is_fb else "answered") + f" · {end:.1f} s"})
        else:
            segs.append({"x0": a["t"], "x1": max(nxt, a["t"] + 0.6), "kind": "error", "label": f"attempt {a['n']}: {a['action']}"})
    return segs


def timeline_png(scenario_id: str, docs: list[dict], catalogue_path: str, out: str, headline: str | None = None,
                 footer: str | None = None, labels: list[str] | None = None, timeout_s: float = 30.0) -> str:
    cat = load_yaml(catalogue_path)
    sc = next(s for s in cat["scenarios"] if s["id"] == scenario_id)
    rows = []
    for k, d in enumerate(docs):
        r = next(x for x in d["scenarios"] if x["id"] == scenario_id)
        rows.append(((labels or [])[k] if labels and k < len(labels) else d["system"]["label"], r))
    W, H = 1200, 660
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    T = lambda x, y, s, **k: ax.text(x, y, s, **{**FONT, **k})  # noqa: E731

    T(60, 62, headline or f"{scenario_id}: {sc['title']}", fontsize=24, fontweight="semibold", color=INK["primary"], va="center")
    T(60, 100, f"{scenario_id} · {sc['fault']}", fontsize=13.5, color=INK["secondary"], va="center")

    px0, px1 = 330, W - 60
    max_el = max(float(r["metrics"]["elapsed_s"]) for _, r in rows)
    xmax = max(max_el * 1.3, 60)
    xs = lambda t: px0 + (px1 - px0) * t / xmax  # noqa: E731
    lane_top, lane_h = 168, 128
    base_y = lane_top + lane_h * len(rows)
    step = 30 if xmax <= 240 else 60
    t = 0
    while t <= xmax:
        ax.plot([xs(t), xs(t)], [lane_top - 6, base_y], color=INK["grid"], linewidth=1, zorder=1)
        T(xs(t), base_y + 16, f"{t:g} s", fontsize=11.5, color=INK["muted"], ha="center", va="center")
        t += step
    ax.plot([px0, px1], [base_y, base_y], color=INK["axis"], linewidth=1, zorder=1)
    T(px0, base_y + 38, "seconds after the request was sent", fontsize=11.5, color=INK["muted"], ha="left", va="center")
    # configured timeout marker
    ax.plot([xs(timeout_s), xs(timeout_s)], [lane_top - 6, base_y], color=INK["axis"], linewidth=1, zorder=1)
    T(xs(timeout_s) + 6, lane_top - 16, f"configured timeout: {timeout_s:g} s", fontsize=11, color=INK["muted"], ha="left", va="center")

    bar_h, r_px = 22, 4
    for i, (label, r) in enumerate(rows):
        y = lane_top + i * lane_h + lane_h / 2 + 8
        m = r["metrics"]; v = r["verdict"]
        first, _, rest = label.partition("\n")
        two = bool(rest)
        T(px0 - 18, y - (26 if two else 12), first, fontsize=13.5, fontweight="semibold", color=INK["primary"], ha="right", va="center")
        if two:
            T(px0 - 18, y - 6, rest, fontsize=12, color=INK["secondary"], ha="right", va="center")
        outcome = {"pass": "complete answer", "partial": "answered, with a caveat", "safe": "clean error, no answer",
                   "fail": "no answer"}[v]
        T(px0 - 18, y + (20 if two else 12), f"{VERDICT[v][0]} {VERDICT[v][3]} · {outcome} · {float(m['elapsed_s']):.1f} s", fontsize=12,
          color=INK["secondary"], ha="right", va="center")
        segs = _segments(r)
        for s_ in segs:
            x0, x1 = xs(s_["x0"]), xs(s_["x1"])
            colour = {"wait": "#d9d8d1", "answer": STATUS["good"], "error": _mix(STATUS["serious"], 0.55)}[s_["kind"]]
            _round_right_bar(ax, x0 + 1, x1 - 1, y, bar_h, colour, r_px)
            if s_["kind"] == "wait":  # label above the bar, anchored at its start
                T(x0 + 2, y - 24, s_["label"], fontsize=11.5, color=INK["secondary"], ha="left", va="center")
            else:  # the outcome: to the right of the bar end, in primary ink
                T(x1 + 8, y + 1, s_["label"], fontsize=12, color=INK["primary"], ha="left", va="center", fontweight="semibold")
        if m["outcome"] != "success":
            xe = xs(float(m["elapsed_s"]))
            ax.plot([xe, xe], [y - 18, y + 18], color=STATUS["critical"], linewidth=2.5, zorder=3)
            txt = f"client gave up · {float(m['elapsed_s']):.0f} s"
            if xe + 9 + _measure(fig, txt, 12, "semibold") <= px1 + 30:
                T(xe + 9, y + 1, txt, fontsize=12, color=INK["primary"], ha="left", va="center", fontweight="semibold")
            else:
                T(xe - 8, y + 26, txt, fontsize=12, color=INK["primary"], ha="right", va="center", fontweight="semibold")

    # legend (measured widths, no overlap)
    ly = base_y + 76
    x = 60
    for colour, text in [("#d9d8d1", "waiting on a primary that never answers"), (STATUS["good"], "answer from the fallback")]:
        ax.add_patch(Rectangle((x, ly - 8), 26, 16, facecolor=colour, edgecolor="none"))
        T(x + 36, ly, text, fontsize=12, color=INK["secondary"], va="center")
        x += 36 + _measure(fig, text, 12) + 34
    ax.plot([x + 6, x + 6], [ly - 10, ly + 10], color=STATUS["critical"], linewidth=2.5)
    T(x + 20, ly, "client gave up (the harness's own limit)", fontsize=12, color=INK["secondary"], va="center")

    T(60, H - 40, footer or "Failover Bench · failoverbench.github.io/failoverbench · one fake provider, sixteen faults, every row reproducible with one command",
      fontsize=11.5, color=INK["muted"], va="center")
    fig.savefig(out, dpi=100, facecolor=SURFACE)
    plt.close(fig)
    return out



# ------------------------------------------------------------------ explainer

def explainer_png(out: str, n_faults: int = 16) -> str:
    """One-glance diagram of how a measurement works."""
    W, H = 1400, 600
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    T = lambda x, y, s, **k: ax.text(x, y, s, **{**FONT, **k})  # noqa: E731
    T(60, 60, "How Failover Bench measures a gateway or SDK", fontsize=24, fontweight="semibold", color=INK["primary"], va="center")
    T(60, 98, "The same request, sixteen times — each time the provider behind the gateway misbehaves in a different, documented way.",
      fontsize=13.5, color=INK["secondary"], va="center")

    boxes = [
        (60, "1 · The runner", "Sends one request per scenario and\nwatches what the caller gets back:\nthe answer, an error, or nothing.", INK["grid"]),
        (520, "2 · The system under test", "Any OpenAI-compatible gateway or SDK,\nwith the same baseline settings:\n2 retries · 30 s timeout · one fallback.", _mix("#2a78d6", 0.16)),
        (980, "3 · The wall (fake provider)", f"Breaks on purpose in {n_faults} ways, chosen\nby model name: 429s, resets, silence,\ncut and stalled streams, bad chunks,\n400s, a primary that flaps.", _mix(STATUS["serious"], 0.22)),
    ]
    bw, bh, by = 360, 178, 150
    for x, title, body, fill in boxes:
        ax.add_patch(Rectangle((x, by), bw, bh, facecolor=fill, edgecolor="none"))
        T(x + 18, by + 30, title, fontsize=14, fontweight="semibold", color=INK["primary"], va="center")
        T(x + 18, by + 60, body, fontsize=12, color=INK["secondary"], va="top", linespacing=1.4)
    # arrows (request goes right, what came back goes left)
    for x0, x1 in ((420, 520), (880, 980)):
        ax.annotate("", xy=(x1 - 6, by + 62), xytext=(x0 + 6, by + 62), arrowprops=dict(arrowstyle="-|>", color=INK["secondary"], lw=1.6))
        ax.annotate("", xy=(x0 + 6, by + 118), xytext=(x1 - 6, by + 118), arrowprops=dict(arrowstyle="-|>", color=INK["muted"], lw=1.2))
        T((x0 + x1) / 2, by + 48, "request", fontsize=10.5, color=INK["secondary"], ha="center", va="center")
    T(470, by + 134, "response", fontsize=10.5, color=INK["muted"], ha="center", va="center")
    T(930, by + 134, "the fault", fontsize=10.5, color=INK["muted"], ha="center", va="center")

    # scoring strip
    sy = by + bh + 52
    T(60, sy, "4 · The score", fontsize=14, fontweight="semibold", color=INK["primary"], va="center")
    T(60, sy + 30, "The runner compares what the caller got with what the wall saw (every attempt, with timings) and applies the scenario's checks:",
      fontsize=12.5, color=INK["secondary"], va="center")
    x = 60
    fs = 12.5
    total = sum(44 + _measure(fig, VERDICT[v][3], fs, "semibold") + 8 + _measure(fig, {"pass": "complete answer", "partial": "answered, with a caveat",
                "safe": "clean error, no answer", "fail": "a hang, or half an answer shown as success"}[v], fs) + 30 for v in ("pass", "partial", "safe", "fail"))
    if total > W - 120:
        fs = 11.5
    for v in ("pass", "partial", "safe", "fail"):
        glyph, tint, chip, word, meaning = VERDICT[v]
        ax.add_patch(Rectangle((x, sy + 52), 34, 22, facecolor=tint, edgecolor="none"))
        T(x + 17, sy + 64, glyph, fontsize=13, color=INK["primary"], ha="center", va="center", fontweight="bold")
        T(x + 44, sy + 63, word, fontsize=fs, fontweight="semibold", color=INK["primary"], va="center")
        short = {"pass": "complete answer", "partial": "answered, with a caveat", "safe": "clean error, no answer",
                 "fail": "a hang, or half an answer shown as success"}[v]
        T(x + 44 + _measure(fig, word, fs, "semibold") + 8, sy + 63, short, fontsize=fs, color=INK["secondary"], va="center")
        x += 44 + _measure(fig, word, fs, "semibold") + 8 + _measure(fig, short, fs) + 30
    T(60, H - 40, "Every healthy answer is the same sixty-word text, so a truncated answer can never pass as a complete one · "
      "failoverbench.github.io/failoverbench", fontsize=11.5, color=INK["muted"], va="center")
    fig.savefig(out, dpi=100, facecolor=SURFACE)
    plt.close(fig)
    return out


# ------------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="failoverbench chart", description="Render shareable PNGs from results.")
    sub = ap.add_subparsers(dest="kind", required=True)
    s1 = sub.add_parser("scorecard")
    s1.add_argument("--results", default="results"); s1.add_argument("--profile", choices=("fast", "full"), default="full")
    s1.add_argument("--catalogue", default="scenarios/catalogue.yaml"); s1.add_argument("--out", default="docs/scorecard.png")
    s1.add_argument("--date", default=None, help="date text for the header (default: newest run date)")
    s1.add_argument("--edition", default="", help='e.g. "October 2026"')
    s3 = sub.add_parser("explainer")
    s3.add_argument("--out", default="docs/how-it-works.png")
    s2 = sub.add_parser("timeline")
    s2.add_argument("results", nargs="+", help="one or more results JSON files (rows, in order)")
    s2.add_argument("--scenario", required=True); s2.add_argument("--catalogue", default="scenarios/catalogue.yaml")
    s2.add_argument("--out", default=None); s2.add_argument("--headline", default=None); s2.add_argument("--footer", default=None)
    s2.add_argument("--labels", nargs="*", default=None, help="lane labels, one per results file")
    s2.add_argument("--timeout", type=float, default=30.0, help="configured timeout to mark, seconds")
    a = ap.parse_args(argv)
    if a.kind == "scorecard":
        print(scorecard_png(a.results, a.profile, a.catalogue, a.out, a.date, a.edition))
    elif a.kind == "explainer":
        print(explainer_png(a.out))
    else:
        docs = []
        for p in a.results:
            with open(p, encoding="utf-8") as fh:
                docs.append(json.load(fh))
        out = a.out or f"docs/timeline-{a.scenario.lower()}.png"
        print(timeline_png(a.scenario, docs, a.catalogue, out, a.headline, a.footer, a.labels, a.timeout))


if __name__ == "__main__":
    main()
