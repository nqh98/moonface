"""Equal-weight cross-asset basket of the frozen MTF headline cell.

Motivation. The single-asset MTF signal (1d trend gate + 15m RSI counter-trend
entry) is a real, persistent BTC L/S edge whose ONLY economic failures are the
program's structural drawdown wall and a sub-1.2 profit factor -- it is a thin
edge wrapped in large single-path drawdown. The program's standing question is
whether a *portfolio structure* relaxes the wall. This module answers it for the
one signal that has both worked out-of-sample and transferred to ETH/SOL: it runs
the SAME frozen cell on each asset (each gated by its OWN 1d trend), scales every
trade to an equal 1/N_assets risk weight, and measures the single faithful equity
path of the merged, time-ordered trade stream.

Equal weight is the only non-data-mined construction -- no per-asset weight is
tuned to the answer. The merged-path drawdown vs the perfect-correlation
reference (the weighted sum of the individual drawdowns) measures how much the
loser-clustering de-correlates across assets. Paper research; promotes nothing to
live."""
from __future__ import annotations

from datetime import datetime, timezone

from moonface.research.mtf.attribute import Trade, path_max_dd, period_stats


def merge_streams(streams: dict[str, list[Trade]], weight: float) -> list[Trade]:
    """Time-ordered union of every asset's trade stream, each net_r scaled by the
    common risk weight (1/N_assets). The result is the basket's single faithful
    trade sequence -- resolving it through period_stats gives the real running
    equity path of an equal-risk book that takes every asset's signals."""
    out: list[Trade] = []
    for trades in streams.values():
        out.extend((ts, side, r * weight) for ts, side, r in trades)
    out.sort(key=lambda t: t[0])
    return out


def diversification(streams: dict[str, list[Trade]], weight: float) -> dict:
    """Merged-path drawdown vs the perfect-correlation reference. ref_dd is the
    weighted sum of each asset's own single-path drawdown -- what the basket
    drawdown WOULD be if every asset bottomed in lockstep. merged_dd below ref
    means the loser-clustering genuinely de-correlates across assets."""
    ref_dd = sum(path_max_dd([r * weight for _, _, r in t])
                 for t in streams.values())
    merged_dd = path_max_dd([r for _, _, r in merge_streams(streams, weight)])
    cut = round(1 - merged_dd / ref_dd, 4) if ref_dd else 0.0
    return {"ref_dd_r": round(ref_dd, 2), "merged_dd_r": merged_dd,
            "dd_cut_frac": cut}


def _year(ts_ms: int) -> int:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).year


def yearly_robustness(merged: list[Trade]) -> tuple[list[dict], float]:
    """Per-calendar-year stats and the robust_frac (share of years with positive
    total R) for the merged basket path -- the same robustness lens the ECON_BAR
    applies to walk-forward windows, here on the honest single path."""
    years = sorted({_year(ts) for ts, _, _ in merged})
    rows, positive = [], 0
    for y in years:
        st = period_stats([t for t in merged if _year(t[0]) == y])
        st["year"] = y
        rows.append(st)
        positive += st["total_r"] > 0
    frac = round(positive / len(years), 4) if years else 0.0
    return rows, frac
