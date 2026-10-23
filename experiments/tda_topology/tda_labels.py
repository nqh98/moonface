"""Frozen-threshold market-level regime labels.

Thresholds are expanding trailing medians, never global quantiles: a global
quantile over the full sample would make the label at bar t depend on bars
after t, which is look-ahead in its purest form.

These thresholds are frozen in the design spec and must never be tuned against
study outcomes -- that would turn the instrument into a fitted regime model,
which is exactly what it is not."""
from __future__ import annotations

import bisect

from moonface.research.microscope.regimes import UNLABELED

BURN_IN = 250       # bars of history before any label is emitted -- FROZEN

LABELS = ("CONCENTRATED/STABLE", "CONCENTRATED/BREAK",
          "DISPERSED/STABLE", "DISPERSED/BREAK")


def expanding_median_flags(values: list[float | None],
                           burn_in: int = BURN_IN) -> list[bool | None]:
    """flags[t] = values[t] > median(all non-None values strictly before t).

    None until `burn_in` observations have accumulated, and None wherever the
    value itself is None. The median uses history before t only, so appending
    future data can never change a past flag."""
    out: list[bool | None] = [None] * len(values)
    hist: list[float] = []
    for t, v in enumerate(values):
        if v is not None and len(hist) >= burn_in:
            n = len(hist)
            med = (hist[n // 2] if n % 2
                   else 0.5 * (hist[n // 2 - 1] + hist[n // 2]))
            out[t] = v > med
        if v is not None:
            bisect.insort(hist, v)
    return out


def build_labels(features: list[dict[str, float | None]],
                 burn_in: int = BURN_IN) -> list[str]:
    """Two frozen axes -> four buckets.

    Concentration: low pers_entropy_h0 = few dominant clusters = CONCENTRATED.
    Stability: large wasserstein_dist = the topology moved = BREAK."""
    hi_entropy = expanding_median_flags(
        [f["pers_entropy_h0"] for f in features], burn_in)
    hi_shift = expanding_median_flags(
        [f["wasserstein_dist"] for f in features], burn_in)
    out: list[str] = []
    for a, b in zip(hi_entropy, hi_shift):
        if a is None or b is None:
            out.append(UNLABELED)
            continue
        out.append(f"{'DISPERSED' if a else 'CONCENTRATED'}/"
                   f"{'BREAK' if b else 'STABLE'}")
    return out
