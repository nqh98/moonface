"""Forward-return-path analysis to choose the MTF hold horizon from statistics.

The grid's 2-day hold was inherited, not derived: the search only ever compared
1d vs 2d. Freely optimizing a hold over a grid would just curve-fit noise. This
instead measures the *shape* of the average forward return the gated entry
produces -- an event-study path E[R(h)] as a function of holding time h -- and
lets the point where that drift is exhausted (marginal gain per day -> 0) pick the
hold. The entry sample is fixed once (non-overlapping at the longest horizon) and
every trade with a full forward window is traced across ALL horizons, so E[R(h)]
is measured on one identical trade set and the per-day marginals are comparable.
Callers split by timestamp into train (selection) and recent (confirmation): a
hold is only trustworthy where both curves flatten in the same place.
"""
from __future__ import annotations

from moonface.core.risk import risk_unit
from moonface.research.drift_screen import event_outcome
from moonface.research.mtf.evaluate import cell_gen
from moonface.research.mtf.grid import MtfCell
from moonface.features.oi_features import nonoverlap
from moonface.research.resrev import mean_z

_BARS_PER_DAY = 96


def forward_path(candles, cell: MtfCell, horizons: list[int],
                 start_ms: int | None = None, end_ms: int | None = None,
                 atr_period: int = 14) -> list[dict]:
    """Per-horizon forward-R stats for the cell's gated entries over one fixed,
    independent trade set. horizons are bar counts (15m). Each row:
      h, days, n, mean_r (E[R] at horizon h), z (mean/(std/sqrt n)),
      marg_per_day (marginal E[R] gain per day vs the previous horizon).
    n is constant across rows: only entries with a full max-horizon forward
    window are kept, so the marginals compare like with like."""
    h_max = max(horizons)
    entries = [(i, side) for i, side in cell_gen(cell)(candles)
               if (start_ms is None or candles[i].timestamp_ms >= start_ms)
               and (end_ms is None or candles[i].timestamp_ms < end_ms)]
    paths: list[list[float]] = []
    for i, side in nonoverlap(entries, h_max):
        if i + h_max >= len(candles):
            continue
        unit = risk_unit(candles, i, 1.0, atr_period)
        if unit is None:
            continue
        sign = 1.0 if side == "LONG" else -1.0
        entry = candles[i].close
        paths.append([sign * (candles[i + h].close - entry) / unit
                      for h in horizons])
    n = len(paths)
    rows, prev_mean, prev_days = [], 0.0, 0.0
    for col, h in enumerate(horizons):
        vals = [p[col] for p in paths]
        mean, z = mean_z(vals)
        days = h / _BARS_PER_DAY
        marg = (mean - prev_mean) / (days - prev_days) if days > prev_days else 0.0
        rows.append({"h": h, "days": round(days, 2), "n": n,
                     "mean_r": round(mean, 4), "z": round(z, 3),
                     "marg_per_day": round(marg, 4)})
        prev_mean, prev_days = mean, days
    return rows


def long_horizon_scan(candles, cell: MtfCell, horizons: list[int],
                      start_ms: int | None = None, end_ms: int | None = None,
                      atr_period: int = 14) -> list[dict]:
    """Per-horizon forward-R stats where EACH horizon draws its own
    non-overlapping entry sample (spacing = that horizon), so n is as large as
    independence allows at every horizon -- essential when horizons span days to
    months (a fixed max-horizon sample would collapse every row to a handful of
    trades). Unlike forward_path the trade set differs across rows, so no marginal
    is reported; per-horizon mean and z are still valid point estimates. longs/
    shorts are tracked because at long holds a directional-beta drift can swamp the
    counter-trend edge if the L/S mix is uneven."""
    entries = [(i, side) for i, side in cell_gen(cell)(candles)
               if (start_ms is None or candles[i].timestamp_ms >= start_ms)
               and (end_ms is None or candles[i].timestamp_ms < end_ms)]
    rows = []
    for h in horizons:
        rs, longs = [], 0
        for i, side in nonoverlap(entries, h):
            out = event_outcome(candles, i, side, h, atr_period)
            if out is not None:
                rs.append(out[0])
                longs += 1 if side == "LONG" else 0
        n = len(rs)
        mean, z = mean_z(rs)
        rows.append({"h": h, "days": round(h / _BARS_PER_DAY, 2), "n": n,
                     "longs": longs, "shorts": n - longs,
                     "mean_r": round(mean, 4), "z": round(z, 3)})
    return rows


def optimal_hold(rows: list[dict], z_floor: float = 1.0) -> dict:
    """The statistically-backed hold: the horizon that maximizes the risk-adjusted
    forward edge. n is constant across horizons here, so z = mean/(std/sqrt n) is
    proportional to mean/std -- argmax z is the per-trade Sharpe-optimal holding
    time. This is robust to the short-horizon noise (a single blip in the mean, or
    a sign-flip in the marginal) that fools a raw-mean argmax or a marginal-<=0
    rule. Reports the raw-E[R] peak for contrast and whether the edge at the
    chosen hold is itself significant (|z| >= z_floor)."""
    zpeak = max(rows, key=lambda r: r["z"])
    peak = max(rows, key=lambda r: r["mean_r"])
    return {"hold_bars": zpeak["h"], "hold_days": zpeak["days"],
            "mean_r": zpeak["mean_r"], "z": zpeak["z"],
            "significant": abs(zpeak["z"]) >= z_floor,
            "raw_peak_days": peak["days"], "raw_peak_mean_r": peak["mean_r"]}
