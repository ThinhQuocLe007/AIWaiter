"""Statistical treatment for the Chapter 5 experiments.

Every number that reaches the thesis passes through here, so that the reporting protocol
declared in §5.1.3 is applied by construction rather than by remembering to apply it:

- proportions carry a Wilson 95% confidence interval, which stays inside [0, 1] and does not
  degenerate as the accuracy approaches 1.0 (the normal approximation does, and most of the
  accuracies in this system are above 0.9);
- two systems measured on the same items are compared with McNemar's exact test on the
  discordant pairs, which is what makes a decisive comparison possible at n < 300;
- anything driven by an LLM is run repeatedly and reported as `mean [min-max]`, because a
  single run of a sampling model reports one draw rather than the system's behaviour;
- latencies are summarised by percentile, never by mean.

Depends only on the standard library, so it imports on the Jetson and in CI without a
scientific stack.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterable, Sequence

# Two-sided normal quantiles. 95% is the thesis default; the others are here so a reviewer
# asking for a different level does not require a code change.
_Z = {0.90: 1.6448536269514722, 0.95: 1.959963984540054, 0.99: 2.5758293035489004}


# --------------------------------------------------------------------------------------
# Proportions
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Proportion:
    """An estimated proportion with its interval, reported as a fraction rather than a float.

    `successes/total` is kept alongside the point estimate because at these sample sizes the
    fraction is the honest presentation: 37/39 says what 0.9487 pretends not to.
    """

    successes: int
    total: int
    confidence: float = 0.95

    @property
    def point(self) -> float:
        return self.successes / self.total if self.total else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.successes, self.total, self.confidence)

    @property
    def half_width(self) -> float:
        lo, hi = self.interval
        return (hi - lo) / 2

    def as_dict(self) -> dict[str, Any]:
        lo, hi = self.interval
        return {
            "successes": self.successes,
            "total": self.total,
            "point": round(self.point, 4),
            "ci_low": round(lo, 4),
            "ci_high": round(hi, 4),
            "confidence": self.confidence,
        }

    def __str__(self) -> str:
        lo, hi = self.interval
        return f"{self.successes}/{self.total} = {self.point:.1%} (95% CI {lo:.1%}-{hi:.1%})"


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the Wald interval throughout: Wald produces intervals that extend past 1.0
    for the high accuracies this system reports, and collapses to zero width at p = 1, which
    would claim certainty from forty observations.
    """
    if total <= 0:
        return (0.0, 0.0)
    z = _Z.get(confidence)
    if z is None:
        raise ValueError(f"unsupported confidence {confidence!r}; use one of {sorted(_Z)}")
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z / denom * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2))
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def required_n(effect: float, p_assumed: float = 0.95, confidence: float = 0.95) -> int:
    """Smallest n whose Wilson half-width is below `effect`, at an assumed accuracy.

    Used to justify the sample sizes in §5.1.2 rather than asserting them: an experiment that
    must resolve a 5-point difference needs an interval narrower than 5 points.
    """
    for n in range(5, 20001):
        if Proportion(round(p_assumed * n), n, confidence).half_width < effect:
            return n
    return 20000


# --------------------------------------------------------------------------------------
# Paired comparison of two systems
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PairedComparison:
    """Outcome of McNemar's exact test between two arms scored on identical items."""

    name_a: str
    name_b: str
    both_correct: int
    a_only: int  # b: A correct, B wrong
    b_only: int  # c: B correct, A wrong
    both_wrong: int
    p_value: float

    @property
    def total(self) -> int:
        return self.both_correct + self.a_only + self.b_only + self.both_wrong

    @property
    def discordant(self) -> int:
        return self.a_only + self.b_only

    @property
    def winner(self) -> str | None:
        if self.a_only == self.b_only:
            return None
        return self.name_a if self.a_only > self.b_only else self.name_b

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "discordant": self.discordant,
            "winner": self.winner,
            "significant": self.significant,
        }

    def __str__(self) -> str:
        if self.discordant == 0:
            return f"{self.name_a} vs {self.name_b}: identical on all {self.total} items"
        verdict = "significant" if self.significant else "not significant"
        return (
            f"{self.name_a} vs {self.name_b}: discordant b={self.a_only}, c={self.b_only} "
            f"(n={self.total}), McNemar exact p={self.p_value:.4g} -> {verdict}"
            + (f", favouring {self.winner}" if self.winner else "")
        )


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts.

    The exact binomial form is used rather than the chi-square approximation because the
    discordant counts here are small (often under 25), where the approximation is unreliable
    and the continuity-corrected variant is conservative.
    """
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * 0.5**n
    return min(1.0, 2 * tail)


def compare_paired(
    name_a: str,
    correct_a: Sequence[bool],
    name_b: str,
    correct_b: Sequence[bool],
) -> PairedComparison:
    """Compare two arms scored item-by-item on the same evaluation set.

    `correct_a[i]` and `correct_b[i]` must refer to the same item; the caller is responsible
    for keeping the order aligned, which is why the arms are run inside a single loop over the
    dataset rather than in separate passes.
    """
    if len(correct_a) != len(correct_b):
        raise ValueError(f"unpaired inputs: {len(correct_a)} vs {len(correct_b)} items")
    both = sum(1 for x, y in zip(correct_a, correct_b) if x and y)
    only_a = sum(1 for x, y in zip(correct_a, correct_b) if x and not y)
    only_b = sum(1 for x, y in zip(correct_a, correct_b) if y and not x)
    neither = sum(1 for x, y in zip(correct_a, correct_b) if not x and not y)
    return PairedComparison(
        name_a=name_a,
        name_b=name_b,
        both_correct=both,
        a_only=only_a,
        b_only=only_b,
        both_wrong=neither,
        p_value=mcnemar_exact(only_a, only_b),
    )


# --------------------------------------------------------------------------------------
# Repeated runs of a stochastic experiment
# --------------------------------------------------------------------------------------


@dataclass
class RunAggregate:
    """Spread of a single metric across repeated runs of a stochastic experiment."""

    metric: str
    values: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.values) if self.values else 0.0

    @property
    def spread(self) -> tuple[float, float]:
        return (min(self.values), max(self.values)) if self.values else (0.0, 0.0)

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.values) if len(self.values) > 1 else 0.0

    def as_dict(self) -> dict[str, Any]:
        lo, hi = self.spread
        return {
            "metric": self.metric,
            "runs": len(self.values),
            "mean": round(self.mean, 4),
            "min": round(lo, 4),
            "max": round(hi, 4),
            "stdev": round(self.stdev, 4),
            "values": [round(v, 4) for v in self.values],
        }

    def __str__(self) -> str:
        lo, hi = self.spread
        return f"{self.metric}: {self.mean:.3f} [{lo:.3f}-{hi:.3f}] over {len(self.values)} runs"


def repeat(
    experiment: Callable[[int], dict[str, float]],
    runs: int = 5,
    on_run: Callable[[int, dict[str, float]], None] | None = None,
) -> dict[str, RunAggregate]:
    """Run a stochastic experiment `runs` times and aggregate each metric it returns.

    `experiment` receives the run index — pass it through to the model as a seed where the
    backend supports one, so that the spread reported is genuine sampling variance and the
    whole experiment stays reproducible from the run indices alone.
    """
    aggregates: dict[str, RunAggregate] = {}
    for i in range(runs):
        metrics = experiment(i)
        for key, value in metrics.items():
            aggregates.setdefault(key, RunAggregate(metric=key)).values.append(float(value))
        if on_run:
            on_run(i, metrics)
    return aggregates


# --------------------------------------------------------------------------------------
# Latency
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LatencySummary:
    """Percentile summary of a latency sample, in milliseconds."""

    label: str
    samples: tuple[float, ...]

    @property
    def p50(self) -> float:
        return percentile(self.samples, 50)

    @property
    def p95(self) -> float:
        return percentile(self.samples, 95)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n": len(self.samples),
            "p50_ms": round(self.p50, 1),
            "p95_ms": round(self.p95, 1),
            "min_ms": round(min(self.samples), 1) if self.samples else 0.0,
            "max_ms": round(max(self.samples), 1) if self.samples else 0.0,
        }

    def __str__(self) -> str:
        return f"{self.label}: p50={self.p50:.0f} ms, p95={self.p95:.0f} ms (n={len(self.samples)})"


def percentile(samples: Iterable[float], q: float) -> float:
    """Linear-interpolated percentile.

    Written out rather than taken from `statistics.quantiles`, which cannot return an exact
    p95 for the sample sizes used here without awkward index arithmetic at the caller.
    """
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q / 100
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


# --------------------------------------------------------------------------------------
# Thesis-table formatting
# --------------------------------------------------------------------------------------


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render a Markdown table ready to paste into the thesis chapter."""
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    head = "| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    body = [
        "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)) + " |" for row in rows
    ]
    return "\n".join([head, rule, *body])


def fmt_proportion(successes: int, total: int) -> str:
    """`37/39 (94.9%, CI 83.1-98.6)` — the reporting form §5.1.3 requires."""
    p = Proportion(successes, total)
    lo, hi = p.interval
    return f"{successes}/{total} ({p.point:.1%}, CI {lo:.1%}-{hi:.1%})"


def fmt_spread(agg: RunAggregate, pct: bool = True) -> str:
    """`94.9% [92.3-97.4]` — mean with observed range across repeated runs."""
    lo, hi = agg.spread
    if pct:
        return f"{agg.mean:.1%} [{lo:.1%}-{hi:.1%}]"
    return f"{agg.mean:.1f} [{lo:.1f}-{hi:.1f}]"
