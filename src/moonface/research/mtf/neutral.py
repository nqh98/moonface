"""Market-neutral (BTC-beta-hedged) overlay for the MTF regime-quality basket.

The MTF counter-trend basket is the strongest signal the program has surfaced,
but its cross-asset "confirmation" on ETH/SOL/DOGE may be crypto *beta* rather
than independent alpha. The program has already been burned by exactly this
confound once: the breadth cross-asset leads looked confirmed on ETH/SOL until a
BTC hedge removed the market component, at which point they went NEGATIVE
(sign-flip) -- the whole apparent edge was beta (`breadth_neutral` finding).

This module applies the SAME falsification to the MTF basket. For each non-BTC
leg it takes the IDENTICAL trade set the basket already trades and subtracts the
BTC component of each trade's PnL over its real holding window, in the same R
units. If the leg's edge survives the hedge it is genuine beta-residual alpha; if
it collapses to ~0 or flips sign, the "confirmation" was crypto beta timing.

BTC itself is un-hedgeable against itself (you cannot market-neutralise the
market), so the BTC leg carries raw in both books and is reported separately.

Reuse: the per-trade hedge arithmetic is `breadth_confirm.neutral.hedge_entries`
(reviewed, and bit-identical to the raw leg at beta=0). This module only adds the
MTF entry generation and a point-in-time *daily* beta estimate appropriate to the
15m base series (a 15m-bar beta window would be both microstructure-noisy and
O(n*window) prohibitive over 226k bars).
"""
from __future__ import annotations

import bisect

from moonface.research.breadth_confirm.neutral import hedge_entries
from moonface.research.mtf.evaluate import cell_gen
from moonface.research.mtf.grid import MtfCell
from moonface.features.oi_features import nonoverlap

DAILY_MS = 86_400_000
BETA_WINDOW_DAYS = 90   # trailing daily returns for the beta estimate (~1 quarter)
BETA_MIN_DAYS = 30      # below this, fall back to unit beta (full hedge)


def daily_returns(candles) -> list[tuple[int, float]]:
    """Close-to-close simple returns of the once-per-UTC-day close series, keyed
    by the day's last-bar timestamp. Point-in-time: the return for day d is known
    only once day d has closed."""
    day_close: dict[int, tuple[int, float]] = {}
    for c in candles:
        day_close[c.timestamp_ms // DAILY_MS] = (c.timestamp_ms, c.close)
    days = sorted(day_close)
    out: list[tuple[int, float]] = []
    for k in range(1, len(days)):
        prev = day_close[days[k - 1]][1]
        ts, close = day_close[days[k]]
        if prev:
            out.append((ts, close / prev - 1.0))
    return out


def rolling_daily_betas(asset_candles, market_candles,
                        window: int = BETA_WINDOW_DAYS,
                        min_days: int = BETA_MIN_DAYS) -> list[tuple[int, float]]:
    """beta_t = cov(asset, market)/var(market) over the trailing `window` DAILY
    returns STRICTLY before day t (the slice a[lo:i] excludes day i's own return,
    so there is no look-ahead). Ascending [(day_ts, beta)]. Falls back to 1.0
    (unit hedge) when var<=0 or obs<min_days."""
    mkt = dict(daily_returns(market_candles))
    aligned = [(ts, ar, mkt[ts]) for ts, ar in daily_returns(asset_candles)
               if ts in mkt]
    a = [x[1] for x in aligned]
    m = [x[2] for x in aligned]
    out: list[tuple[int, float]] = []
    for i, (ts, _, _) in enumerate(aligned):
        lo = max(0, i - window)
        am, mm = a[lo:i], m[lo:i]
        n = len(mm)
        if n < min_days:
            out.append((ts, 1.0))
            continue
        mbar, abar = sum(mm) / n, sum(am) / n
        var = sum((x - mbar) ** 2 for x in mm)
        if var <= 0.0:
            out.append((ts, 1.0))
            continue
        cov = sum((am[k] - abar) * (mm[k] - mbar) for k in range(n))
        out.append((ts, cov / var))
    return out


def beta_lookup_for(entries, asset_candles, market_candles,
                    window: int = BETA_WINDOW_DAYS,
                    min_days: int = BETA_MIN_DAYS) -> dict[int, float]:
    """{entry_ts -> point-in-time beta} for a set of (i, side) entries. The beta
    is the most recent daily estimate whose day-timestamp is <= the entry bar's
    timestamp; because each daily beta already excludes its own day's return, this
    uses only information available before the entry. Returns unit beta before any
    daily estimate exists."""
    betas = rolling_daily_betas(asset_candles, market_candles, window, min_days)
    day_ts = [t for t, _ in betas]
    lut: dict[int, float] = {}
    for i, _side in entries:
        ets = asset_candles[i].timestamp_ms
        pos = bisect.bisect_right(day_ts, ets) - 1
        lut[ets] = betas[pos][1] if pos >= 0 else 1.0
    return lut


def hedged_leg(asset_candles, market_candles, cell: MtfCell,
               beta: float | None = None) -> dict:
    """Resolve the cell's entries on `asset_candles`, hedge each trade's BTC
    component, and return {raw, hedged, betas, n_skipped, entries} where raw and
    hedged are lists of {i, side, net_r, atr_frac}. `beta` overrides the estimate
    (beta=0.0 is the correctness anchor: hedged == raw). Restricted to
    span-resolvable exits (the frozen basket cells use horizon_hold /
    horizon_wide_stop); regime_flip is not hedgeable through this path."""
    if cell.exit_name == "regime_flip":
        raise ValueError("regime_flip exit is not span-resolvable; hedge the "
                         "horizon_hold / horizon_wide_stop basket cells")
    entries = list(nonoverlap(cell_gen(cell)(asset_candles), cell.h))
    lut = None if beta is not None else beta_lookup_for(
        entries, asset_candles, market_candles)
    res = hedge_entries(asset_candles, market_candles, entries,
                        cell.exit_name, cell.exit_params,
                        beta=beta, beta_lookup=lut)
    res["entries"] = entries
    return res
