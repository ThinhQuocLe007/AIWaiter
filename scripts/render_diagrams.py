#!/usr/bin/env python3
"""Render every ```plantuml block in docs/thesis/diagram.md to docs/thesis/images/.

Each block is named by its `title Figure N` line, so Figure 7 always lands in
images/Figure7.svg and re-running overwrites in place (stable filenames for the
thesis document's figure references).

Usage:
    python scripts/render_diagrams.py                 # SVG, all figures
    python scripts/render_diagrams.py --format png    # PNG instead
    python scripts/render_diagrams.py --only 4 5 12   # just those figures
    python scripts/render_diagrams.py --check         # validate syntax, write nothing

Requires plantuml.jar. Point PLANTUML_JAR at it, or drop it next to this script.
Layout uses PlantUML's built-in `smetana` engine so Graphviz (`dot`) is NOT
required — without it PlantUML fails with
"Cannot run program /opt/local/bin/dot" on every non-sequence diagram.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "thesis" / "diagram.md"
IMAGES = ROOT / "docs" / "thesis" / "images"

BLOCK_RE = re.compile(r"```plantuml\n(.*?)```", re.S)
# Figures are named by their "## Figure N" markdown heading, not by an in-diagram
# `title` line — the rendered SVG carries no title (captions live in the document),
# so the filename must come from the surrounding prose. 5a / 5b / 10a / 10b are distinct.
FIGURE_HEADING_RE = re.compile(r"^##\s+Figure\s+(\d+[a-z]?)\b", re.M)


def find_jar() -> Path:
    env = os.getenv("PLANTUML_JAR")
    candidates = [Path(env)] if env else []
    candidates += [Path(__file__).resolve().parent / "plantuml.jar", ROOT / "plantuml.jar"]
    for c in candidates:
        if c.is_file():
            return c
    sys.exit(
        "plantuml.jar not found. Download it from https://plantuml.com/download "
        "and set PLANTUML_JAR=/path/to/plantuml.jar (or place it in scripts/)."
    )


# A4 portrait with standard margins: the text block a figure has to fit into.
TEXT_BLOCK_W_CM = 15.0
TEXT_BLOCK_H_CM = 22.0
SVG_PX_PER_INCH = 96.0
VIEWBOX_RE = re.compile(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"')
FONTSIZE_RE = re.compile(r"skinparam\s+defaultFontSize\s+(\d+)")


def effective_pt(svg: str, source: str) -> float | None:
    """Label size in points once the figure is scaled to fit the A4 text block.

    A diagram is laid out at its natural size, then shrunk to fit the page. What survives that
    shrink is what the examiner reads, so the useful measure is not the figure's own font setting
    but that setting times the fit scale. Returns None if the SVG has no viewBox.
    """
    m = VIEWBOX_RE.search(svg[:1200])
    if not m:
        return None
    w_cm = float(m.group(1)) / SVG_PX_PER_INCH * 2.54
    h_cm = float(m.group(2)) / SVG_PX_PER_INCH * 2.54
    fit = min(TEXT_BLOCK_W_CM / w_cm, TEXT_BLOCK_H_CM / h_cm)
    base = FONTSIZE_RE.search(source)
    return (int(base.group(1)) if base else 12) * fit


def extract(only: set[str] | None) -> dict[str, str]:
    if not SOURCE.is_file():
        sys.exit(f"missing source: {SOURCE}")
    text = SOURCE.read_text(encoding="utf-8")
    # Each ```plantuml block takes its name from the nearest "## Figure N" heading
    # above it, so filenames stay stable (Figure8.svg) with no in-diagram title.
    headings = [(m.start(), m.group(1)) for m in FIGURE_HEADING_RE.finditer(text)]
    figures: dict[str, str] = {}
    for i, m in enumerate(BLOCK_RE.finditer(text), 1):
        pos = m.start()
        fig = next((hid for hpos, hid in reversed(headings) if hpos < pos), None)
        name = f"Figure{fig}" if fig else f"Block{i}"
        if name in figures:
            sys.exit(f"duplicate figure {name!r} — two plantuml blocks map to one heading")
        figures[name] = m.group(1)
    if only:
        wanted = {f"Figure{n}" for n in only}
        missing = wanted - figures.keys()
        if missing:
            sys.exit(f"no such figure(s): {', '.join(sorted(missing))}")
        figures = {k: v for k, v in figures.items() if k in wanted}
    return figures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format", default="svg", choices=("svg", "png"), help="output format (default: svg)")
    ap.add_argument("--only", nargs="+", metavar="N", help="render only these figure numbers")
    ap.add_argument("--check", action="store_true", help="validate syntax + legibility, write nothing")
    ap.add_argument(
        "--min-pt", type=float, default=8.0, metavar="PT",
        help="minimum effective label size once scaled into the A4 text block (default: 8.0)",
    )
    args = ap.parse_args()

    jar = find_jar()
    figures = extract(set(args.only) if args.only else None)
    if not figures:
        sys.exit("no plantuml blocks found")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for name, body in figures.items():
            (tmpdir / f"{name}.puml").write_text(body, encoding="utf-8")

        outdir = tmpdir / "out"
        proc = subprocess.run(
            [
                "java", "-jar", str(jar),
                f"-t{args.format}",
                "-Playout=smetana",
                "-o", str(outdir),
                *[str(tmpdir / f"{n}.puml") for n in figures],
            ],
            capture_output=True,
            text=True,
        )
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)

        failed = []
        for name in figures:
            produced = outdir / f"{name}.{args.format}"
            if not produced.is_file():
                failed.append((name, "no output produced"))
                continue
            # PlantUML reports a syntax error by rendering an error image, exit code 0.
            if args.format == "svg":
                svg = produced.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"Syntax Error|Error line", svg):
                    failed.append((name, "syntax error (see rendered output)"))
                    continue
                eff = effective_pt(svg, figures[name])
                if eff is not None:
                    if eff < args.min_pt:
                        failed.append((name, f"too dense: {eff:.1f} pt at A4 width (need >= {args.min_pt:.1f})"))
                        continue
                    print(f"  {name}  {eff:.1f} pt", end="")
            if not args.check:
                IMAGES.mkdir(parents=True, exist_ok=True)
                shutil.copy2(produced, IMAGES / produced.name)
                print(f"  -> docs/thesis/images/{produced.name}")
            else:
                print()

        if failed:
            print(file=sys.stderr)
            for name, why in failed:
                print(f"FAIL {name}: {why}", file=sys.stderr)
            print(
                "\nA figure below the threshold will not be readable in print. Split it into two "
                "figures, move explanatory notes into the caption, or shorten the widest labels — "
                "raising the font size alone does NOT help, since the whole canvas grows with it.",
                file=sys.stderr,
            )
            return 1

    verb = "validated" if args.check else "rendered"
    print(f"{verb} {len(figures)} diagram(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
