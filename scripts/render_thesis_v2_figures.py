#!/usr/bin/env python3
"""Render the hand-drawn thesis_v2 architecture figures to docs/thesis_v2/images/.

These figures used to be hand-written SVG with no source, so when the code moved the
figures silently went stale: the cart state machine still showed DRAFTING as a stage
that is "never entered", the router still showed the ten context features that were
dropped on 2026-07-29, and the validator still showed three outcomes when the router
has four. Keeping the geometry in code means a figure can be re-derived when the
component it describes changes.

Filenames are stable, so re-running overwrites in place and the markdown references
in docs/thesis_v2/ keep working. Both SVG (referenced by the markdown) and PNG (for
the Word export) are written.

Usage:
    python scripts/render_thesis_v2_figures.py                  # all three
    python scripts/render_thesis_v2_figures.py router validator # just those

Ground truth for each figure is cited in the docstring of its builder below.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "thesis_v2" / "images"

FONT = "DejaVu Sans, Verdana, sans-serif"
INK = "#37474F"          # box outlines and edges
TEXT = "#212121"         # text inside a node
LABEL = "#455A64"        # text on an edge
RED = "#C62828"          # a transition that is refused

GREEN = "#C8E6C9"        # accepting / terminal-good
YELLOW = "#FFF9C4"       # waiting on the guest
BLUE = "#BBDEFB"         # committed, or a learned component
ORANGE = "#FFE0B2"       # not yet read back to the guest, or a delegated turn
PINK = "#F8BBD0"         # gave up
PURPLE = "#E1BEE7"       # a language-model call
DIAMOND = "#FBE9E7"      # decision
GREY = "#ECEFF1"         # start


class Canvas:
    """Minimal flowchart primitives. All coordinates are absolute."""

    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" '
            f'fill="#FFFFFF"/>'
        ]

    # ── text ────────────────────────────────────────────────────────────────
    @staticmethod
    def _width(s: str, size: float) -> float:
        return len(s) * size * 0.525

    def _text(self, x, y, s, size=12, anchor="middle", bold=False, color=TEXT):
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}"{weight} '
            f'fill="{color}" text-anchor="{anchor}" dominant-baseline="central">{s}</text>'
        )

    def lines(self, cx, cy, rows, size=12, anchor="middle", color=TEXT, gap=16):
        """Vertically centred block of text rows."""
        top = cy - (len(rows) - 1) * gap / 2
        for i, row in enumerate(rows):
            self._text(cx, top + i * gap, row, size, anchor, color=color)

    def label(self, x, y, rows, anchor="start", size=12, bg=True, color=LABEL):
        """Edge label, optionally on a white patch so it survives crossing a line."""
        for i, row in enumerate(rows):
            yy = y + i * 16
            if bg:
                bw = self._width(row, size) + 8
                bx = {"start": x - 4, "middle": x - bw / 2, "end": x - bw + 4}[anchor]
                self.parts.append(
                    f'<rect x="{bx}" y="{yy - 9}" width="{bw}" height="18" '
                    f'fill="#FFFFFF" stroke="none"/>'
                )
            self._text(x, yy, row, size, anchor, color=color)

    def vlabel(self, x, y, s, size=12):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{LABEL}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'transform="rotate(-90 {x} {y})">{s}</text>'
        )

    # ── nodes ───────────────────────────────────────────────────────────────
    def box(self, x, y, w, h, rows, fill="#FFFFFF", rx=3, size=12, bold_first=False):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="1.2"/>'
        )
        cx, cy = x + w / 2, y + h / 2
        if bold_first:
            self._text(cx, cy - 10, rows[0], 13, bold=True)
            self.lines(cx, cy + 11, rows[1:], 11)
        else:
            self.lines(cx, cy, rows, size)
        return (x, y, x + w, y + h)

    def state(self, x, y, w, title, sub, fill, tsize=15, ssize=12, h=66):
        """A state-machine state: bold name over a one-line gloss."""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" '
            f'fill="{fill}" stroke="{INK}" stroke-width="1.2"/>'
        )
        self._text(x + w / 2, y + 24.5, title, tsize, bold=True)
        self._text(x + w / 2, y + 41.5, sub, ssize)

    def terminal(self, x, y, w, h, title, sub, fill):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" ry="{h / 2}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="1.2"/>'
        )
        self._text(x + w / 2, y + h / 2 - 10, title, 13, bold=True)
        self._text(x + w / 2, y + h / 2 + 10, sub, 11)

    def diamond(self, cx, cy, hw, hh, rows, size=12):
        pts = f"{cx - hw},{cy} {cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh}"
        self.parts.append(
            f'<polygon points="{pts}" fill="{DIAMOND}" stroke="{INK}" stroke-width="1.2"/>'
        )
        self.lines(cx, cy, rows, size)

    def parallelogram(self, cx, cy, w, h, row, skew=18):
        x0, y0 = cx - w / 2, cy - h / 2
        pts = (f"{x0 + skew},{y0} {x0 + w + skew},{y0} "
               f"{x0 + w - skew},{y0 + h} {x0 - skew},{y0 + h}")
        self.parts.append(
            f'<polygon points="{pts}" fill="#FFFFFF" stroke="{INK}" stroke-width="1.2"/>'
        )
        self._text(cx, cy, row, 13)

    def dot(self, cx, cy, final=False):
        if final:
            self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="12" fill="none" '
                              f'stroke="{INK}" stroke-width="1.4"/>')
            self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{INK}"/>')
        else:
            self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="{INK}"/>')

    # ── edges ───────────────────────────────────────────────────────────────
    def _head(self, x, y, d, color):
        if d == "down":
            pts = f"{x},{y} {x - 2.9},{y - 6.4} {x + 2.9},{y - 6.4}"
        elif d == "up":
            pts = f"{x},{y} {x - 2.9},{y + 6.4} {x + 2.9},{y + 6.4}"
        elif d == "right":
            pts = f"{x},{y} {x - 6.4},{y - 2.9} {x - 6.4},{y + 2.9}"
        else:
            pts = f"{x},{y} {x + 6.4},{y - 2.9} {x + 6.4},{y + 2.9}"
        self.parts.append(f'<polygon points="{pts}" fill="{color}"/>')

    def edge(self, pts, d, width=1.2, dash=None, color=INK, head=True):
        path = "M " + " L ".join(f"{a} {b}" for a, b in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round"{da}/>'
        )
        if head:
            self._head(pts[-1][0], pts[-1][1], d, color)

    def cross(self, cx, cy, r=8, color=RED):
        self.parts.append(
            f'<path d="M {cx - r} {cy - r} L {cx + r} {cy + r} '
            f'M {cx + r} {cy - r} L {cx - r} {cy + r}" '
            f'stroke="{color}" stroke-width="2.2" fill="none"/>'
        )

    # ── output ──────────────────────────────────────────────────────────────
    def write(self, name: str) -> None:
        svg = IMAGES / f"{name}.svg"
        svg.write_text("".join(self.parts) + "</svg>")
        try:
            import cairosvg
        except ImportError:
            print(f"  {svg.name} written; cairosvg missing, PNG not refreshed")
            return
        cairosvg.svg2png(url=str(svg), write_to=str(IMAGES / f"{name}.png"),
                         output_width=self.w, output_height=self.h)
        print(f"  {svg.name} + {name}.png")


# ═══════════════════════════════════════════════════════════════════════════
def cart_state_machine() -> None:
    """Figure 4.7. The four order stages and every transition between them.

    Ground truth:
      - state_outcome_node._compute_order_stage is the single writer of order_stage.
      - graph.set_cart writes DRAFTING for a tablet edit, never AWAITING_CONFIRMATION.
      - deterministic_validator_node refuses confirm_order unless the stage is
        AWAITING_CONFIRMATION, which is the dashed edge.
      - a SEARCH/PAYMENT/RETRY turn holds AWAITING_CONFIRMATION when the cart has
        items, so only a chat turn or a failed cart operation drops back to DRAFTING.
    """
    c = Canvas(960, 700)

    c.dot(250, 50)
    c.state(100, 87, 300, "IDLE", "no items in the cart", GREEN)
    c.state(100, 297, 300, "DRAFTING", "the cart holds items not read back yet",
            ORANGE, ssize=11)
    c.state(540, 297, 320, "AWAITING CONFIRMATION",
            "the cart has been read back to the guest", YELLOW, tsize=14)
    c.state(540, 507, 320, "CONFIRMED", "the order is with the kitchen", BLUE)
    c.dot(700, 650, final=True)

    c.edge([(250, 59), (250, 87)], "down")
    c.label(258, 70, ["a party is seated"])

    # A voice order adds and reads back in the same turn.
    c.edge([(400, 110), (700, 110), (700, 297)], "down")
    c.label(550, 80, ["the first item is added,", "the cart is read back"], "middle")

    # A tablet edit has not been read back yet.
    c.edge([(250, 153), (250, 297)], "down")
    c.label(258, 208, ["the guest edits the cart", "by hand on the tablet"])

    c.edge([(400, 318), (540, 318)], "right")
    c.label(470, 274, ["add or remove succeeds,", "the cart is read back"], "middle")

    c.edge([(540, 342), (400, 342)], "left")
    c.label(470, 373, ["a chat turn, or a cart", "operation that failed"], "middle")

    # A search or payment question between the order and the confirmation holds the
    # stage, so the confirmation that follows is not refused as unasked.
    c.edge([(570, 363), (570, 398), (630, 398), (630, 363)], "up")
    c.label(600, 418, ["a search or payment turn,", "the cart untouched"], "middle")

    c.edge([(160, 363), (160, 398), (240, 398), (240, 363)], "up")
    c.label(200, 418, ["the cart is not touched"], "middle")

    c.edge([(760, 297), (760, 265), (830, 265), (830, 297)], "down")
    c.label(795, 233, ["further add or remove,", "the cart is read back"], "middle")

    c.edge([(100, 330), (55, 330), (55, 120), (100, 120)], "right")
    c.vlabel(41, 225, "clear_cart empties the cart")

    c.edge([(600, 297), (600, 200), (340, 200), (340, 153)], "up")
    c.label(470, 182, ["clear_cart empties the cart"], "middle")

    c.edge([(700, 363), (700, 507)], "down", width=2.6)
    c.label(710, 412, ["the guest confirms", "the only edge into CONFIRMED"])

    c.edge([(330, 363), (330, 540), (540, 540)], "right", dash="6 4", color=RED)
    c.cross(436, 540)
    c.label(400, 572, ["a confirmation from DRAFTING is refused;",
                       "the guest must be shown the cart first"], "middle", color=RED)

    c.edge([(860, 540), (910, 540), (910, 330), (860, 330)], "left")
    c.vlabel(924, 435, "another item is added")

    c.edge([(700, 573), (700, 637)], "down")
    c.label(710, 592, ["payment verified,", "the session closes"])

    c.write("cart_state_machine")


# ═══════════════════════════════════════════════════════════════════════════
def router_flow() -> None:
    """Figure 4.4. Utterance to intent queue.

    Ground truth:
      - classifier/model.py: INPUT_DIM == EMBEDDING_DIM == 768. The ten context
        features and their scaler were removed on 2026-07-29.
      - classifier_router_node: CLASSIFIER_THRESHOLD 0.7, SEARCH_THRESHOLD 0.85,
        and has_boundary_markers gates the fast path independently of confidence.
    """
    c = Canvas(1000, 830)
    cx, bx, bw = 340, 168, 344

    c.parallelogram(cx, 38, 342, 46, "Utterance and conversation state")
    c.box(bx, 101, bw, 50, ["Vietnamese word segmentation"])
    c.box(bx, 189, bw, 50, ["Bi-encoder: a 768-dimension vector"], BLUE)
    c.box(bx, 277, bw, 62, ["MLP over the 768 inputs:",
                            "a probability for each of four intents"], BLUE)

    c.edge([(cx, 61), (cx, 101)], "down")
    c.edge([(cx, 151), (cx, 189)], "down")
    c.edge([(cx, 239), (cx, 277)], "down")
    c.edge([(cx, 339), (cx, 368)], "down")

    # The bar is class-specific: SEARCH is held to 0.85 because dish-name tokens
    # pull the MLP toward SEARCH on utterances that are really ORDER.
    c.diamond(cx, 432, 210, 64, ["Confidence at or above its threshold",
                                 "(0.85 for SEARCH, 0.70 otherwise)",
                                 "and no clause-boundary marker?"])

    c.edge([(130, 432), (60, 432), (60, 570)], "down")
    c.label(122, 414, ["yes"], "end")
    c.terminal(15, 570, 280, 60, "Fast path", "one intent, no model call", GREEN)

    c.edge([(550, 432), (760, 432), (760, 570)], "down")
    c.label(558, 414, ["no"])
    c.box(600, 570, 320, 60, ["Rewriter model splits the",
                              "utterance into fragments"], PURPLE)
    c.edge([(760, 630), (760, 668)], "down")
    c.box(600, 668, 320, 50, ["Classify each fragment"], BLUE)
    c.edge([(760, 718), (760, 756)], "down")
    c.terminal(600, 756, 320, 60, "Queue of intents", "worked through in order", GREEN)

    c.write("router_flow")


# ═══════════════════════════════════════════════════════════════════════════
def validator_flow() -> None:
    """Figure 4.5. A proposed tool call from the worker to one of four outcomes.

    Ground truth:
      - graph._route_after_validator has four exits in this order: circuit breaker
        (loop_count >= MAX_RETRY_LOOPS), tools (is_valid), chat_worker (the
        validator set delegate_reason), and back to the current worker.
      - deterministic_validator_node strips confirm_order when it shares a turn with
        any of {add_cart, remove_cart, clear_cart}, not add_cart alone.
      - add_cart resolves names against the menu; remove_cart resolves against the
        current cart (_resolve_remove_name); clear_cart resolves no name at all.
    """
    c = Canvas(1200, 1120)
    cx = 400
    bx, bw = 230, 340        # trunk boxes
    rx, rw = 700, 330        # side boxes

    c.box(bx, 18, bw, 44, ["Tool calls proposed by the worker"], GREY, rx=22, size=13)

    c.edge([(cx, 62), (cx, 88)], "down")
    c.diamond(cx, 140, 190, 52, ["A cart change and a",
                                 "confirmation in one turn?"])
    c.edge([(590, 140), (rx, 140)], "right")
    c.label(600, 122, ["yes"])
    c.box(rx, 110, rw, 60, ["Strip the confirmation and",
                            "re-queue it behind the change"])
    c.edge([(865, 170), (865, 258), (570, 258)], "left")

    c.edge([(cx, 192), (cx, 232)], "down")
    c.label(cx + 8, 212, ["no"])
    c.box(bx, 232, bw, 52, ["Apply this tool's preconditions"])

    # The two cart tools that resolve a name resolve it against different sources.
    c.edge([(cx, 284), (cx, 310)], "down")
    c.diamond(cx, 356, 155, 46, ["Adding to the cart?"])
    c.edge([(555, 356), (rx, 356)], "right")
    c.label(600, 338, ["yes"])
    c.box(rx, 318, rw, 76, ["Resolve every name against the",
                            "menu (Figure 4.6), then repair",
                            "the cart"])

    c.edge([(cx, 402), (cx, 434)], "down")
    c.label(cx + 8, 418, ["no"])
    c.diamond(cx, 480, 165, 46, ["Removing from the cart?"])
    c.edge([(565, 480), (rx, 480)], "right")
    c.label(600, 462, ["yes"])
    c.box(rx, 454, rw, 52, ["Resolve the name against",
                            "the current cart"])

    c.edge([(cx, 526), (cx, 556)], "down")
    c.label(cx + 8, 541, ["no"])
    c.diamond(cx, 600, 150, 44, ["Any errors?"])

    # Both resolution branches rejoin above the error check.
    c.edge([(1030, 356), (1080, 356), (1080, 600), (550, 600)], "left")
    c.edge([(865, 506), (865, 600)], "right", head=False)

    c.edge([(250, 600), (135, 600), (135, 1030)], "down")
    c.label(242, 582, ["none"], "end")

    c.edge([(cx, 644), (cx, 686)], "down")
    c.label(cx + 8, 665, ["yes"])
    c.box(bx, 686, bw, 56, ["Count the attempt and write",
                            "feedback naming the problem"])

    c.edge([(cx, 742), (cx, 768)], "down")
    c.diamond(cx, 812, 150, 44, ["Third failure in a row?"])
    c.edge([(550, 812), (1025, 812), (1025, 1030)], "down")
    c.label(560, 794, ["yes"])

    # The fourth exit: a rejection the worker cannot fix by rewriting its call.
    c.edge([(cx, 856), (cx, 894)], "down")
    c.label(cx + 8, 875, ["no"])
    c.diamond(cx, 940, 154, 46, ["A fact about the state,",
                                 "not a fault in the call?"])
    c.edge([(554, 940), (695, 940), (695, 1030)], "down")
    c.label(564, 922, ["yes"])

    c.edge([(cx, 986), (cx, 1030)], "down")
    c.label(cx + 8, 1008, ["no"])

    c.terminal(15, 1030, 240, 60, "Approved", "the tool node runs the call", GREEN)
    c.terminal(280, 1030, 240, 60, "Back to the worker", "with the feedback", YELLOW)
    c.terminal(560, 1030, 270, 60, "Delegate to the chat worker",
               "the turn ends at the validator", ORANGE)
    c.terminal(870, 1030, 310, 60, "Circuit breaker",
               "the guest hears an apology", PINK)

    c.write("validator_flow")


FIGURES = {
    "cart": cart_state_machine,
    "router": router_flow,
    "validator": validator_flow,
}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(FIGURES)
    unknown = [n for n in wanted if n not in FIGURES]
    if unknown:
        sys.exit(f"unknown figure(s): {', '.join(unknown)}. "
                 f"choose from: {', '.join(FIGURES)}")
    for name in wanted:
        print(f"{name}:")
        FIGURES[name]()
