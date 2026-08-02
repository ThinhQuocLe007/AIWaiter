#!/usr/bin/env python3
"""Render the Chapter 5 result figures from the JSON files in evals/results/.

Every figure is drawn from the most recent result file of its family, so the
workflow after re-running an experiment is:

    PYTHONPATH=. uv run python evals/scripts/eval_router_arms.py
    PYTHONPATH=. uv run python evals/scripts/render_ch5_figures.py

and the SVG in docs/thesis_v2/images/ is up to date. Filenames are stable, so
the figure references in the chapter never have to change.

The script also writes docs/thesis_v2/05-experiments-results/figure-data.md,
which holds every number each figure was drawn from, already formatted as the
markdown table rows the chapter uses. Swapping a re-run into the thesis is then
a copy of those rows into the matching table rather than a hunt through prose.

Output is plain SVG in the visual style of the Chapter 4 diagrams: white
ground, #37474F strokes at 1.2, Material 100-level pastel fills, DejaVu Sans.
No third-party dependency, so it runs anywhere the repository runs.

    python evals/scripts/render_ch5_figures.py             # all results
    python evals/scripts/render_ch5_figures.py --only 2 5  # just those
    python evals/scripts/render_ch5_figures.py --list      # show source files
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"
IMAGES = ROOT / "docs" / "thesis_v2" / "images"
DATA_NOTE = ROOT / "docs" / "thesis_v2" / "05-experiments-results" / "figure-data.md"

FONT = "DejaVu Sans, Verdana, sans-serif"
INK = "#212121"
MUTED = "#455A64"
STROKE = "#37474F"
GRID = "#B0BEC5"
WHITE = "#FFFFFF"

BLUE = "#BBDEFB"
GREEN = "#C8E6C9"
YELLOW = "#FFF9C4"
PEACH = "#FBE9E7"
PURPLE = "#E1BEE7"
RED = "#FFCDD2"
TEAL = "#B2DFDB"
PALE = "#ECEFF1"

# A4 text block is 15 cm wide. At 96 px/in a 760 px figure scales to about 0.75,
# which keeps a 14 px label at roughly 10.5 pt on the printed page.
W = 760


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SVG:
    """A minimal SVG canvas. Enough primitives for bars, points and axes."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.parts: list[str] = [f'<rect width="{w}" height="{h}" fill="{WHITE}"/>']

    def rect(self, x, y, w, h, fill=WHITE, stroke=STROKE, sw=1.2, rx=0):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        r = f' rx="{rx}" ry="{rx}"' if rx else ""
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{r} fill="{fill}"{st}/>'
        )

    def line(self, x1, y1, x2, y2, stroke=STROKE, sw=1.2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def circle(self, cx, cy, r, fill=WHITE, stroke=STROKE, sw=1.2):
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def text(self, x, y, s, size=13, fill=INK, anchor="middle", weight=None, style=None):
        w = f' font-weight="{weight}"' if weight else ""
        st = f' font-style="{style}"' if style else ""
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="central"{w}{st}>'
            f"{esc(s)}</text>"
        )

    def save(self, path: Path) -> None:
        body = "".join(self.parts)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">{body}</svg>'
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")


def latest(pattern: str) -> Path | None:
    """Most recently modified JSON result of a family, or None if absent."""
    files = [Path(f) for f in glob.glob(str(RESULTS / pattern)) if f.endswith(".json")]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def load(pattern: str) -> tuple[dict, str] | tuple[None, None]:
    p = latest(pattern)
    if p is None:
        return None, None
    return json.loads(p.read_text(encoding="utf-8")), p.name


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - s) / d, (c + s) / d


def fmt_p(p: float) -> str:
    """A p-value at the precision a thesis table should carry."""
    if p >= 0.001:
        return f"{p:.3f}"
    e = math.floor(math.log10(p))
    return f"{p / 10**e:.1f} × 10^{e}"


# --------------------------------------------------------------------------
# Figure 5.1 — router ablation: accuracy against median latency
# --------------------------------------------------------------------------
def fig1(rows: list[str]) -> str | None:
    d, src = load("router_arms_*")
    if d is None:
        return None

    arms = d["arms"]
    # Arm E (MLP + context) is gone: it ran the same text-only model as D through a `state`
    # argument predict.classify() ignores, so it could only ever return D's labels. Older
    # result files still carry it, hence the filter rather than a plain list.
    order = [k for k in ("A", "B", "C", "D", "F") if k in arms]
    # The labels in the result file carry the full model tag and overrun the label column.
    # Keep them short here, but read the model names from the run so a model swap follows.
    slm = str(d.get("slm_model", "SLM")).replace("-instruct", "")
    llm = str(d.get("llm_model", "LLM")).replace("-instruct", "")
    short = {
        "A": "Centroid, semantic only",
        "B": f"SLM only, {slm}",
        "C": "Hybrid semantic to SLM",
        "D": "MLP, text-only (proposed)",
        "F": f"LLM zero-shot, {llm}",
    }
    pts = []
    for k in order:
        a = arms[k]
        acc = a["accuracy"]
        pts.append(
            {
                "key": k,
                "label": short.get(k, a["label"]),
                "full": a["label"],
                "acc": acc["point"],
                # Recomputed here rather than read from the result file. eval_router_arms.py stores
                # ci_low/ci_high rounded to 4 decimals, and formatting that to 1 decimal can land on
                # an exact tie: 0.8125 -> 81.25 -> banker's rounding gives 81.2 where the unrounded
                # 81.254 gives 81.3. Recomputing from k and n removes the double round.
                **dict(zip(("lo", "hi"), wilson(acc["successes"], acc["total"]))),
                "k": acc["successes"],
                "n": acc["total"],
                "p50": a["latency"]["p50_ms"],
                "p95": a["latency"]["p95_ms"],
            }
        )

    # Three of the five arms sit within a few milliseconds of each other, so a scatter over
    # latency collapses them into one blob. One row per arm keeps every arm legible, with
    # accuracy and cost as two panels a reader scans left to right.
    ROW = 46
    T = 118
    h = T + len(pts) * ROW + 74
    s = SVG(W, h)

    AX0, AX1 = 258, 448          # accuracy panel
    AVAL = 462                   # accuracy value column
    LX0, LX1 = 548, 648          # latency panel, log scale
    LVAL = 660                   # latency value column
    lo_y, hi_y = 0.60, 0.95
    lo_x = math.log10(min(p["p50"] for p in pts) * 0.6)
    hi_x = math.log10(max(p["p95"] for p in pts) * 1.5)

    def A(v):
        return AX0 + (v - lo_y) / (hi_y - lo_y) * (AX1 - AX0)

    def X(ms):
        return LX0 + (math.log10(ms) - lo_x) / (hi_x - lo_x) * (LX1 - LX0)

    s.text(30, 26, "Five routing systems on one paired case set", size=14, anchor="start")
    s.text(30, 48, f"n = {pts[0]['n']} cases, identical for every arm.",
           size=12, fill=MUTED, anchor="start")
    s.text(AX0, 82, "accuracy, Wilson 95 % CI", size=12, fill=MUTED, anchor="start")
    s.text(LX0, 82, "latency, log scale", size=12, fill=MUTED, anchor="start")

    bot = T + len(pts) * ROW
    for v in (0.60, 0.70, 0.80, 0.90):
        s.line(A(v), T - 6, A(v), bot, stroke=GRID, sw=0.6)
        s.text(A(v), bot + 18, f"{v * 100:.0f}%", size=11, fill=MUTED)
    last = None
    for ms in (10, 100, 1000):
        if lo_x <= math.log10(ms) <= hi_x:
            x = X(ms)
            s.line(x, T - 6, x, bot, stroke=GRID, sw=0.6)
            if last is None or x - last > 44:   # decade labels can collide on a short axis
                s.text(x, bot + 18, f"{ms} ms", size=11, fill=MUTED)
                last = x

    for i, p in enumerate(pts):
        y = T + i * ROW + ROW / 2
        proposed = p["key"] == "D"
        fill = GREEN if proposed else BLUE
        s.text(36, y, p["key"], size=13, fill=INK, anchor="start",
               weight="bold" if proposed else None)
        s.text(54, y, p["label"], size=12, fill=INK if proposed else MUTED, anchor="start",
               weight="bold" if proposed else None)

        s.rect(AX0, y - 9, max(1.5, A(p["acc"]) - AX0), 18, fill=fill,
               sw=1.6 if proposed else 1.2)
        s.line(A(p["lo"]), y, A(p["hi"]), y, stroke=STROKE, sw=1.2)
        for b in (p["lo"], p["hi"]):
            s.line(A(b), y - 6, A(b), y + 6, stroke=STROKE, sw=1.2)
        s.text(AVAL, y, f"{p['acc'] * 100:.1f} %", size=12, anchor="start",
               weight="bold" if proposed else None)

        s.line(X(p["p50"]), y, X(p["p95"]), y, stroke=STROKE, sw=1.2)
        s.line(X(p["p95"]), y - 5, X(p["p95"]), y + 5, stroke=STROKE, sw=1.2)
        s.circle(X(p["p50"]), y, 6, fill=fill, sw=1.6 if proposed else 1.2)
        s.text(LVAL, y, f"{p['p50']:.0f} / {p['p95']:.0f} ms", size=10.5, fill=MUTED,
               anchor="start")

    s.line(30, bot + 34, W - 30, bot + 34, stroke=GRID, sw=0.8)
    s.text(30, bot + 56, "Dot is the median, whisker the 95th percentile. "
                         "The proposed arm is D.", size=11, fill=MUTED, anchor="start")
    s.save(IMAGES / "ch5_router_ablation.svg")

    rows.append(f"### Figure 5.1 — router ablation\n\nSource: `{src}`, n = {pts[0]['n']} paired cases.\n")
    rows.append("| Arm | System | Accuracy | 95 % Wilson CI | p50 (ms) | p95 (ms) |")
    rows.append("|-----|--------|----------|---------------:|---------:|---------:|")
    for p in pts:
        bold = "**" if p["key"] == "D" else ""
        rows.append(
            f"| {bold}{p['key']}{bold} | {bold}{p['label']}{bold} | "
            f"{bold}{p['k']}/{p['n']}, {p['acc'] * 100:.1f} %{bold} | "
            f"{bold}{p['lo'] * 100:.1f}–{p['hi'] * 100:.1f} %{bold} | "
            f"{bold}{p['p50']:.1f}{bold} | {bold}{p['p95']:.1f}{bold} |"
        )
    rows.append("")
    if d.get("comparisons"):
        rows.append("McNemar against the proposed arm:")
        rows.append("")
        rows.append("| Comparison | b/c | p |")
        rows.append("|---|:---:|---:|")
        for c in d["comparisons"]:
            rows.append(
                f"| {c['name_a']} vs {c['name_b']} | {c['a_only']}/{c['b_only']} | "
                f"{fmt_p(c['p_value'])} |"
            )
        rows.append("")
    return src


# --------------------------------------------------------------------------
# Table 5.3 — single-intent confusion matrix and per-class metrics
#
# Not a figure. A 4x4 grid of small integers reads better as a table than as a
# heatmap, and the claim it supports is about which cells are zero rather than
# about magnitude. The numbers are still emitted here so a re-run reaches the
# chapter the same way every other result does.
# --------------------------------------------------------------------------
def tbl_confusion(rows: list[str]) -> str | None:
    d, src = load("mlp_router_eval_*")
    if d is None or "single_intent" not in d:
        return None
    si = d["single_intent"]
    cm = si["confusion_matrix"]
    labels = ["ORDER", "SEARCH", "PAYMENT", "CHAT"]

    lo, hi = wilson(si["correct"], si["total"])
    rows.append(f"### Table 5.3 — single-intent accuracy\n\nSource: `{src}`.\n")
    rows.append(f"Accuracy {si['correct']}/{si['total']} = {si['accuracy'] * 100:.1f} %, "
                f"Wilson {lo * 100:.1f}–{hi * 100:.1f} %. "
                f"p50 {si['latency_p50_ms']} ms, p95 {si['latency_p95_ms']} ms, "
                f"mean confidence {si['mean_confidence']}.\n")
    rows.append("| True \\ Predicted | " + " | ".join(labels) + " | Total |")
    rows.append("|---|" + ":---:|" * (len(labels) + 1))
    for r in labels:
        vals = [int(cm[r].get(c, 0)) for c in labels]
        cells = " | ".join(f"**{v}**" if labels[i] == r else str(v) for i, v in enumerate(vals))
        rows.append(f"| **{r}** | {cells} | {sum(vals)} |")
    rows.append("")
    rows.append("| Class | Precision | Recall | F1 |")
    rows.append("|---|---:|---:|---:|")
    for c in labels:
        pc = si["per_class"][c]
        rows.append(f"| {c} | {pc['precision']:.3f} | {pc['recall']:.3f} | {pc['f1']:.3f} |")
    rows.append("")

    if "multi_intent_detection" in d:
        m = d["multi_intent_detection"]
        rows.append("Multi-intent detection, same run: "
                    f"{m['detected_total']}/{m['true_multi_count']} detected "
                    f"({m['detection_rate'] * 100:.1f} %), "
                    f"{m['detected_by_boundary']} by boundary marker, "
                    f"{m['detected_by_low_conf']} by low confidence; "
                    f"{m['false_alarms']} false alarms on {m['pseudo_multi_count']} controls.\n")
    return src


# --------------------------------------------------------------------------
# Table 5.7 — validator ablation
#
# Not a figure. Six integers, two of which are zero, and a bar of length zero
# reads worse than a table cell containing "0".
# --------------------------------------------------------------------------
def tbl_validator(rows: list[str]) -> str | None:
    on, src_on = load("validator_ablation_validator_on_*")
    off, src_off = load("validator_ablation_validator_off_*")
    if on is None or off is None:
        return None

    def g(d, key):
        return d["summary"][key]["mean"]

    groups = [
        ("Off-menu items reaching a cart tool",
         g(on, "off_menu_items_in_cart_tools"), g(off, "off_menu_items_in_cart_tools")),
        ("Bad confirm_order calls",
         g(on, "bad_confirm_order_count"), g(off, "bad_confirm_order_count")),
    ]
    pass_on = g(on, "pass_rate")
    pass_off = g(off, "pass_rate")

    rows.append(f"### Table 5.7 — validator ablation\n\nSources: `{src_on}`, `{src_off}`.\n")
    rows.append("| Condition | Scenario pass rate | Off-menu items reaching cart tools | Bad `confirm_order` calls |")
    rows.append("|-----------|:------------------:|:----------------------------------:|:-----------------------:|")
    rows.append(f"| Validator ON | {pass_on * 100:.1f} % | **{groups[0][1]:.0f}** | {groups[1][1]:.0f} |")
    rows.append(f"| Validator OFF | {pass_off * 100:.1f} % | **{groups[0][2]:.0f}** | **{groups[1][2]:.0f}** |")
    rows.append("")
    return f"{src_on} / {src_off}"


# --------------------------------------------------------------------------
# Figure 5.2 — retrieval quality by difficulty
# --------------------------------------------------------------------------
def fig4(rows: list[str]) -> str | None:
    d, src = load("retrieval_full_*")
    if d is None:
        return None
    per = d["summary"]["per_difficulty"]["rrf"]
    modes = d["summary"]["modes"]

    diffs = [k for k in ("easy", "medium", "hard") if k in per]
    # All four quality metrics, so the figure carries everything the table it replaced did.
    metrics = [("precision", "P@5", YELLOW), ("recall", "R@5", BLUE),
               ("mrr", "MRR", PURPLE), ("hit_rate", "hit rate", TEAL)]

    # Key spellings have shifted across revisions of the harness, so accept the aliases
    # rather than silently reporting a metric as zero when only its old name is present.
    ALIASES = {
        "precision": ("precision", "precision_at_k", "p_at_5"),
        "recall": ("recall", "recall_at_k", "r_at_5"),
        "mrr": ("mrr",),
        "hit_rate": ("hit_rate", "hitrate"),
    }

    def get(bucket, key):
        for k in ALIASES.get(key, (key,)):
            if k in bucket:
                return bucket[k]
        raise KeyError(f"{key} missing from result file; tried {ALIASES.get(key, (key,))}")

    # per_difficulty carries a normalised weight rather than a count, so take n from the
    # per-query records instead.
    counts: dict[str, int] = {}
    for rec in d.get("detailed", []):
        counts[rec.get("difficulty", "?")] = counts.get(rec.get("difficulty", "?"), 0) + 1

    h = 430
    s = SVG(W, h)
    L, T, B = 70, 76, 96
    pw, ph = W - L - 40, h - T - B
    gw = pw / len(diffs)
    bw = min(46, gw / (len(metrics) + 1.4))

    s.text(30, 26, "Retrieval quality collapses on the queries the menu text cannot answer",
           size=14, anchor="start")
    s.text(30, 48, "Fused BM25 + FAISS ranking, by query difficulty.", size=12,
           fill=MUTED, anchor="start")

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = T + ph - frac * ph
        s.line(L, y, L + pw, y, stroke=GRID, sw=0.6)
        s.text(L - 10, y, f"{frac:.2f}", size=11, fill=MUTED, anchor="end")
    s.line(L, T + ph, L + pw, T + ph, sw=1.2)

    for i, dif in enumerate(diffs):
        bucket = per[dif]
        n = counts.get(dif, "")
        gx = L + i * gw
        for j, (key, name, fill) in enumerate(metrics):
            v = get(bucket, key)
            x = gx + gw / 2 - (len(metrics) * bw) / 2 + j * bw
            bh = v * ph
            s.rect(x, T + ph - bh, bw - 6, bh, fill=fill, sw=1.2)
            s.text(x + (bw - 6) / 2, T + ph - bh - 12, f"{v:.2f}", size=11, fill=INK)
        s.text(gx + gw / 2, T + ph + 22, f"{dif}" + (f"  (n = {n})" if n else ""),
               size=12, fill=INK)

    lx = L
    for _, name, fill in metrics:
        s.rect(lx, h - 44, 16, 12, fill=fill, sw=1.0)
        s.text(lx + 22, h - 38, name, size=12, fill=MUTED, anchor="start")
        lx += 22 + len(name) * 7 + 30
    s.save(IMAGES / "ch5_retrieval_difficulty.svg")

    rows.append(f"### Figure 5.2 — retrieval by difficulty\n\nSource: `{src}`.\n")
    rows.append("| Mode | P@5 | R@5 | MRR | Hit rate |")
    rows.append("|------|:----:|:----:|:----:|:--------:|")
    for key, name in (("bm25", "BM25 only"), ("faiss", "FAISS only"), ("rrf", "**RRF fusion**")):
        m = modes[key]
        b = "**" if key == "rrf" else ""
        rows.append(
            f"| {name} | {b}{get(m, 'precision'):.3f}{b} | {b}{get(m, 'recall'):.3f}{b} | "
            f"{b}{get(m, 'mrr'):.3f}{b} | {b}{get(m, 'hit_rate'):.3f}{b} |"
        )
    rows.append("")
    rows.append("| Difficulty | n | P@5 | R@5 | MRR | Hit rate |")
    rows.append("|------------|:--:|:----:|:----:|:----:|:--------:|")
    for dif in diffs:
        b = per[dif]
        rows.append(
            f"| {dif.capitalize()} | {counts.get(dif, '')} | "
            f"{get(b, 'precision'):.3f} | {get(b, 'recall'):.3f} | "
            f"{get(b, 'mrr'):.3f} | {get(b, 'hit_rate'):.3f} |"
        )
    rows.append("")
    gk = d["summary"]["gatekeeper"]
    rows.append(f"Gatekeeper: both lanes {gk['both']}, lexical only {gk['lexical_only']}, "
                f"semantic only {gk['semantic_only']}, rejected {gk['rejected']}, "
                f"admitted {gk['passed']}/{gk['total']}.\n")
    return src


# --------------------------------------------------------------------------
# Figure 5.3 — turn latency by intent against the budget
# --------------------------------------------------------------------------
def fig5(rows: list[str]) -> str | None:
    d, src = load("latency_*")
    if d is None:
        return None
    per = d["per_intent_summary"]
    g = d["global"]
    BUDGET = 5.0

    items = list(per.items())
    ROW = 44
    T = 116
    h = T + len(items) * ROW + 96
    s = SVG(W, h)
    L = 150
    VAL = W - 126            # value labels share one column so they read as a table
    pw = VAL - L - 24

    # A single stalled run can put a p95 far outside the budget and flatten every other bar.
    # Clip the axis at a readable multiple of the budget and mark whatever overflows, rather
    # than letting one outlier decide the scale.
    worst = max(v["p95"] for _, v in items)
    top = min(worst * 1.08, BUDGET * 1.6)
    clipped = worst > top

    def X(sec):
        return L + min(sec, top) / top * pw

    step = next(st for st in (0.5, 1.0, 2.0, 5.0) if top / st <= 9)

    s.text(30, 26, "Turn latency by intent class against the five-second budget", size=14,
           anchor="start")
    s.text(30, 48, "Bar is the median, whisker reaches the 95th percentile.", size=12,
           fill=MUTED, anchor="start")

    bot = T + len(items) * ROW
    n_tick = int(top / step)
    for i in range(n_tick + 1):
        sec = i * step
        x = X(sec)
        s.line(x, T - 10, x, bot + 4, stroke=GRID, sw=0.6)
        s.text(x, bot + 22, f"{sec:g} s", size=11, fill=MUTED)

    if BUDGET <= top:
        xb = X(BUDGET)
        s.line(xb, T - 24, xb, bot + 4, stroke="#EF5350", sw=1.4, dash="5 4")
        s.text(xb, T - 34, "budget 5 s", size=12, fill="#C62828")

    y = T
    for name, v in items:
        s.text(L - 14, y + 14, name, size=12, fill=INK, anchor="end")
        s.text(L - 14, y + 30, f"n = {v['n']}", size=10, fill=MUTED, anchor="end")
        s.rect(L, y + 5, max(2.0, X(v["p50"]) - L), 21, fill=BLUE, sw=1.2)
        s.line(X(v["p50"]), y + 16, X(v["p95"]), y + 16, stroke=STROKE, sw=1.2)
        if v["p95"] > top:
            xe = X(top)
            s.parts.append(
                f'<polygon points="{xe - 9:.1f},{y + 10:.1f} {xe:.1f},{y + 16:.1f} '
                f'{xe - 9:.1f},{y + 22:.1f}" fill="{STROKE}"/>'
            )
        else:
            s.line(X(v["p95"]), y + 9, X(v["p95"]), y + 23, stroke=STROKE, sw=1.2)
        s.text(VAL, y + 16, f"{v['p50']:.2f} / {v['p95']:.2f} s", size=11, fill=MUTED,
               anchor="start")
        y += ROW

    s.line(30, bot + 38, W - 30, bot + 38, stroke=GRID, sw=0.8)
    s.text(30, bot + 60, f"All turns: p50 {g['p50_s']:.2f} s, p95 {g['p95_s']:.2f} s, "
                         f"n = {g['n']}.", size=12, fill=INK, anchor="start")
    if clipped:
        s.text(30, bot + 80, f"An arrowhead marks a 95th percentile beyond the axis; "
                             f"the largest is {worst:.2f} s.", size=11, fill=MUTED,
               anchor="start")
    s.save(IMAGES / "ch5_latency_by_intent.svg")

    rows.append(f"### Figure 5.3 — turn latency by intent\n\nSource: `{src}`, "
                f"{d.get('n_runs_per_utterance', '?')} runs per utterance.\n")
    rows.append("| Intent | p50 | p95 | Measurements |")
    rows.append("|--------|:-----:|:-----:|:--:|")
    for name, v in items:
        rows.append(f"| {name} | {v['p50']:.2f} s | {v['p95']:.2f} s | {v['n']} |")
    rows.append(f"| **All turns** | **{g['p50_s']:.2f} s** | **{g['p95_s']:.2f} s** | "
                f"**{g['n']}** |")
    rows.append("")
    return src


# --------------------------------------------------------------------------
# Figure 5.4 — where the turn budget is spent
# --------------------------------------------------------------------------
def fig6(rows: list[str]) -> str | None:
    d, src = load("latency_*")
    if d is None or "per_node_summary" not in d:
        return None
    nodes = d["per_node_summary"]
    ranked = sorted(nodes.items(), key=lambda kv: -kv[1].get("pct_of_total", 0))
    CUT = 0.5
    items = [(k, v) for k, v in ranked if v.get("pct_of_total", 0) >= CUT]
    dropped = [k for k, v in ranked if v.get("pct_of_total", 0) < CUT]

    ROW = 38
    T = 104
    h = T + len(items) * ROW + 84
    s = SVG(W, h)
    L = 178
    # Bars stop short of the value column so a long node name can never push text off the page.
    PCT, DETAIL = 470, 528
    pw = PCT - L - 58
    top = max(v["pct_of_total"] for _, v in items)

    s.text(30, 26, "Which graph node consumes the turn", size=14, anchor="start")
    s.text(30, 48, "Share of total measured turn time, with the node's own median and "
                   "95th percentile.", size=12, fill=MUTED, anchor="start")

    fills = [BLUE, GREEN, YELLOW, PEACH, PURPLE, TEAL, PALE]
    y = T
    for i, (name, v) in enumerate(items):
        s.text(L - 14, y + 13, name.replace("_", " "), size=12, fill=INK, anchor="end")
        w = max(2.0, v["pct_of_total"] / top * pw)
        s.rect(L, y, w, 26, fill=fills[i % len(fills)], sw=1.2)
        s.text(PCT, y + 13, f"{v['pct_of_total']:.1f} %", size=12, weight="bold", anchor="end")
        s.text(DETAIL, y + 13, f"p50 {v['p50_s']:.2f} s    p95 {v['p95_s']:.2f} s",
               size=11, fill=MUTED, anchor="start")
        y += ROW

    s.line(30, y + 10, W - 30, y + 10, stroke=GRID, sw=0.8)
    if dropped:
        names = ", ".join(n.replace("_", " ") for n in sorted(dropped))
        s.text(30, y + 34, f"Below {CUT:g} % of the turn and omitted: {names}.",
               size=11, fill=MUTED, anchor="start")
    s.save(IMAGES / "ch5_latency_by_node.svg")

    rows.append(f"### Figure 5.4 — turn budget by graph node\n\nSource: `{src}`.\n")
    rows.append("| Node | Share of turn | p50 | p95 | n |")
    rows.append("|------|:---:|:---:|:---:|:--:|")
    for name, v in sorted(nodes.items(), key=lambda kv: -kv[1].get("pct_of_total", 0)):
        rows.append(f"| `{name}` | {v['pct_of_total']:.1f} % | {v['p50_s']:.3f} s | "
                    f"{v['p95_s']:.3f} s | {v['n']} |")
    rows.append("")
    return src


# Numbered in the order the figures appear in the chapter, which is why the confusion
# matrix is 5.1 and the ablation 5.2 while their functions keep their original names.
# Every producer emits its numbers into figure-data.md. Only those with an svg
# filename also draw one: a result earns a figure when it shows something a table
# cannot, which here means a two-dimensional trade-off, a trend across an ordered
# variable, a comparison against a threshold, or a gap of several orders of
# magnitude. Everything else stays a table.
PRODUCERS = {
    1: ("Table 5.3, single-intent accuracy", None, tbl_confusion),
    2: ("Figure 5.1, router ablation", "ch5_router_ablation.svg", fig1),
    3: ("Table 5.7, validator ablation", None, tbl_validator),
    4: ("Figure 5.2, retrieval by difficulty", "ch5_retrieval_difficulty.svg", fig4),
    5: ("Figure 5.3, turn latency by intent", "ch5_latency_by_intent.svg", fig5),
    6: ("Figure 5.4, turn budget by graph node", "ch5_latency_by_node.svg", fig6),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", type=int, help="producer numbers, see --list")
    ap.add_argument("--list", action="store_true",
                    help="show which result file each figure would read, and exit")
    args = ap.parse_args()

    if args.list:
        for pat in ("router_arms_*", "mlp_router_eval_*", "validator_ablation_validator_on_*",
                    "validator_ablation_validator_off_*", "retrieval_full_*", "latency_*"):
            p = latest(pat)
            print(f"{pat:42s} -> {p.name if p else 'MISSING'}")
        return 0

    wanted = set(args.only) if args.only else set(PRODUCERS)
    rows: list[str] = [
        "# Chapter 5 result data",
        "",
        "Generated by `evals/scripts/render_ch5_figures.py`. Every number below was read from",
        "the result file named beneath its heading, and every figure and table in the chapter",
        "was drawn from the same numbers. The tables are formatted as the chapter uses them,",
        "so bringing a re-run into the thesis is a copy of the rows into the matching table.",
        "",
        "Not every result is a figure. Those that stayed tables are listed here too, because",
        "they need refreshing after a re-run just as much as the figures do.",
        "",
        "Do not hand-edit this file. Re-run the script instead.",
        "",
    ]

    made, missing = [], []
    for n in sorted(wanted):
        if n not in PRODUCERS:
            print(f"no producer {n}", file=sys.stderr)
            continue
        label, fname, fn = PRODUCERS[n]
        src = fn(rows)
        if src is None:
            missing.append((n, label))
            print(f"  skip   {label} — no result file")
        else:
            made.append((n, label, src))
            print(f"  {'wrote ' if fname else 'numbers'} {label}  from {src}")

    DATA_NOTE.parent.mkdir(parents=True, exist_ok=True)
    DATA_NOTE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    drawn = sum(1 for n, _, _ in made if PRODUCERS[n][1])
    print(f"\n{drawn} figure(s) in {IMAGES.relative_to(ROOT)}")
    print(f"numbers for all {len(made)} result(s) written to {DATA_NOTE.relative_to(ROOT)}")
    if missing:
        print(f"{len(missing)} result(s) skipped for want of a result file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
