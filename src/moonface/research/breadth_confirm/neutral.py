"""Beta-hedge overlay for the market-neutral falsification.

Takes the *identical* breadth-lead trade set on a traded asset and removes the
crypto-market (BTC) component of each trade's PnL over its actual holding window,
so we can test whether the breadth signal predicts the asset's beta-RESIDUAL or
merely rides crypto beta. Reuses `resolve_trade_span` (net_r identical to
`single_trade_r`), so beta=0 reproduces the raw cross-asset result exactly.
"""
from __future__ import annotations

from collections.abc import Callable

from moonface.core.metrics import resolve_trade_span

BETA_WINDOW: int = 500   # trailing 4h bars (~83 days) for the beta estimate
BETA_MIN_OBS: int = 60   # below this, fall back to unit beta (full hedge)


def simple_returns(candles) -> list[tuple[int, float]]:
    """Close-to-close simple returns keyed by the *later* bar's timestamp."""
    out: list[tuple[int, float]] = []
    for j in range(1, len(candles)):
        prev = candles[j - 1].close
        if prev:
            out.append((candles[j].timestamp_ms, candles[j].close / prev - 1.0))
    return out


def aligned_returns(asset_candles, market_candles) -> list[tuple[int, float, float]]:
    """(ts, asset_ret, market_ret) on the timestamps present in both series."""
    mkt = dict(simple_returns(market_candles))
    out: list[tuple[int, float, float]] = []
    for ts, ar in simple_returns(asset_candles):
        mr = mkt.get(ts)
        if mr is not None:
            out.append((ts, ar, mr))
    return out


def rolling_betas(aligned: list[tuple[int, float, float]],
                  window: int = BETA_WINDOW,
                  min_obs: int = BETA_MIN_OBS) -> dict[int, float]:
    """beta_t = cov(asset, market)/var(market) over the `window` returns STRICTLY
    before ts (no look-ahead). Falls back to 1.0 when var≈0 or obs<min_obs."""
    betas: dict[int, float] = {}
    a = [x[1] for x in aligned]
    m = [x[2] for x in aligned]
    for i, (ts, _, _) in enumerate(aligned):
        lo = max(0, i - window)
        am = a[lo:i]
        mm = m[lo:i]
        n = len(mm)
        if n < min_obs:
            betas[ts] = 1.0
            continue
        mbar = sum(mm) / n
        abar = sum(am) / n
        var = sum((x - mbar) ** 2 for x in mm)
        if var <= 0.0:
            betas[ts] = 1.0
            continue
        cov = sum((am[k] - abar) * (mm[k] - mbar) for k in range(n))
        betas[ts] = cov / var
    return betas


def hedge_entries(
    asset_candles,
    market_candles,
    entries: list[tuple[int, str]],
    exit_name: str,
    exit_params: dict,
    beta: float | None = None,
    beta_lookup: dict[int, float] | None = None,
    window: int = BETA_WINDOW,
    min_obs: int = BETA_MIN_OBS,
) -> dict:
    """Resolve each (i, side) on `asset_candles`, then subtract the BTC component
    of its PnL over [entry_ts, exit_ts] in the same R units.

    Beta source, in priority order: a constant `beta` (e.g. 0.0 for the raw
    correctness gate); a precomputed `beta_lookup` keyed by entry timestamp
    (so betas can use full-history trailing windows while trades resolve within a
    slice); else a rolling beta computed from the passed series. Returns
    {"hedged", "raw", "betas", "n_skipped"}.
    """
    mkt_close = {c.timestamp_ms: c.close for c in market_candles}
    rolling = None
    if beta is None and beta_lookup is None:
        rolling = rolling_betas(
            aligned_returns(asset_candles, market_candles), window, min_obs)

    hedged: list[dict] = []
    raw: list[dict] = []
    used_betas: list[float] = []
    n_skipped = 0
    for i, side in entries:
        span = resolve_trade_span(asset_candles, i, side, exit_name, exit_params)
        if span is None:
            n_skipped += 1
            continue
        entry_idx, exit_idx, net_r, atr_frac = span
        entry_ts = asset_candles[entry_idx].timestamp_ms
        exit_ts = asset_candles[exit_idx].timestamp_ms
        be, bx = mkt_close.get(entry_ts), mkt_close.get(exit_ts)
        raw.append({"i": i, "side": side, "net_r": net_r, "atr_frac": atr_frac})
        if be is None or bx is None or be == 0 or atr_frac <= 0:
            # No aligned market quote -> cannot hedge; carry the raw leg.
            hedged.append({"i": i, "side": side, "net_r": net_r, "atr_frac": atr_frac})
            continue
        if beta is not None:
            b = beta
        elif beta_lookup is not None:
            b = beta_lookup.get(entry_ts, 1.0)
        else:
            b = rolling.get(entry_ts, 1.0)
        used_betas.append(b)
        sign = 1.0 if side == "LONG" else -1.0
        market_ret = bx / be - 1.0
        hedged_net_r = net_r - sign * b * market_ret / atr_frac
        # No rounding: beta=0 must be bit-identical to the raw leg (the gate).
        hedged.append({"i": i, "side": side,
                       "net_r": hedged_net_r, "atr_frac": atr_frac})
    return {"hedged": hedged, "raw": raw, "betas": used_betas, "n_skipped": n_skipped}


def entries_provider(spec_key: str) -> Callable:
    """The matching entry builder for each lead (non-overlap vs overlapping)."""
    from moonface.research.breadth_internal.evaluate import cell_entries
    from moonface.research.breadth_internal.hf_evaluate import hf_cell_entries
    return {"net_new_highs": cell_entries}.get(spec_key, hf_cell_entries)
