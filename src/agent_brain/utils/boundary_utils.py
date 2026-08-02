"""Shared boundary-marker detection for multi-intent utterance splitting.

Used by ``classifier_router_node`` (deployed agent) and ``eval_mlp_router``
(evaluation harness). Originally copy-pasted in both files; consolidated here
to eliminate the duplication and keep the regex in one place.

Sentence terminators (``?``, ``.``, ``!``, ``\\n``) were added 2026-07-29
because 4/27 true multi-intent utterances split only by punctuation — e.g.
``"Hàu nướng có những kiểu nào? Cho mình kiểu phô mai với 1 phần"`` — were
not being detected. The rewriter LLM handles decomposition; this function
just gates whether it is invoked.

Comma-separated clauses and teencode abbreviations (``r`` → ``rồi``,
``vs`` → ``với``, ``xog`` → ``xong``) were added 2026-07-31 because
8 of 25 multi-intent eval cases used commas or teencode without explicit
conjunctions and were silently reduced to a single intent on the fast path.
"""

from __future__ import annotations

import re

_MULTI_CLAUSE_RE = re.compile(
    r"\b(rồi thì|với lại|rồi|và|thì|xong|vs)\b"
    r"|\br\b"
    r"|\bxog\b"
    r"|à mà"
    r"|,\s*mà\b"
    r"|[?.!\n]"
)

_COMMA_CLAUSE_RE = re.compile(r",\s")


def has_boundary_markers(utterance: str) -> bool:
    """Return True when the utterance contains a clause-boundary signal.

    Conjunctions (rồi, và, thì, xong, ...), teencode abbreviations
    (r, vs, xog), and sentence terminators (?, ., !, \\n) count as
    boundaries — but only when there is substantial text on both sides
    (≥ 2 words).

    A comma alone between two substantial clauses is also treated as a
    boundary, even without an explicit conjunction.  The rewriter LLM
    handles whether the clauses are truly separate intents; a false
    positive here costs one LLM call, whereas a false negative drops
    the second intent entirely.

    ``rồi`` at the end of an utterance is an aspect particle
    ("hết nhiêu tiền rồi em ơi"), not a clause boundary, and the 2-word
    check catches it.
    """
    low = utterance.lower()
    for m in _MULTI_CLAUSE_RE.finditer(low):
        before = low[:m.start()].split()
        after = low[m.end():].split()
        if len(before) >= 2 and len(after) >= 2:
            return True
    for m in _COMMA_CLAUSE_RE.finditer(low):
        before = low[:m.start()].split()
        after = low[m.end():].split()
        if len(before) >= 2 and len(after) >= 2:
            return True
    return False
