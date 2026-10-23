from __future__ import annotations

from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.research.microscope.features import dist_from_ma, pct_returns, rolling_z
from moonface.research.sse.universe import MembershipSchedule

Z_WINDOW = 540
Z_MIN_FRAC = 0.9
MA_PERIOD = 300
RET_BARS = 6
MIN_ACTIVE = 30


@dataclass(frozen=True)
class AxisMatrix:
    timestamps: list[int]
    raw_breadth: list[float | None]
    raw_disp: list[float | None]
    breadth_z: list[float | None]
    disp_z: list[float | None]
    active_counts: list[int]


def _close_maps(pool: dict[str, DataBundle]) -> dict[str, dict[int, float]]:
    return {
        sym: {c.timestamp_ms: c.close for c in bundle.candles}
        for sym, bundle in pool.items()
    }


def build_axes(
    pool: dict[str, DataBundle],
    membership: MembershipSchedule,
    *,
    ma_period: int = MA_PERIOD,
    ret_bars: int = RET_BARS,
    z_window: int = Z_WINDOW,
    min_frac: float = Z_MIN_FRAC,
    min_active: int = MIN_ACTIVE,
) -> AxisMatrix:
    """Cross-sectional breadth/dispersion on a shared timestamp axis."""
    close_maps = _close_maps(pool)
    above_maps: dict[str, dict[int, float | None]] = {}
    ret_maps: dict[str, dict[int, float | None]] = {}
    for sym, bundle in pool.items():
        closes = [c.close for c in bundle.candles]
        dists = dist_from_ma(closes, period=ma_period)
        rets = pct_returns(closes, ret_bars)
        ts = [c.timestamp_ms for c in bundle.candles]
        above_maps[sym] = {t: (1.0 if d is not None and d > 0 else 0.0 if d is not None else None)
                           for t, d in zip(ts, dists)}
        ret_maps[sym] = {t: r for t, r in zip(ts, rets)}
    raw_breadth: list[float | None] = []
    raw_disp: list[float | None] = []
    active_counts: list[int] = []
    for idx, ts in enumerate(membership.timestamps):
        members = membership.at(idx)
        active = [sym for sym in members if close_maps.get(sym, {}).get(ts) is not None]
        active_counts.append(len(active))
        if len(active) < min_active:
            raw_breadth.append(None)
            raw_disp.append(None)
            continue
        above = [above_maps.get(sym, {}).get(ts) for sym in active]
        above_vals = [v for v in above if v is not None]
        raw_breadth.append(
            sum(above_vals) / len(above_vals) if len(above_vals) >= min_active else None
        )
        rets = [ret_maps.get(sym, {}).get(ts) for sym in active]
        ret_vals = [v for v in rets if v is not None]
        if len(ret_vals) >= min_active:
            mean = sum(ret_vals) / len(ret_vals)
            raw_disp.append((sum((r - mean) ** 2 for r in ret_vals) / len(ret_vals)) ** 0.5)
        else:
            raw_disp.append(None)
    return AxisMatrix(
        timestamps=list(membership.timestamps),
        raw_breadth=raw_breadth,
        raw_disp=raw_disp,
        breadth_z=rolling_z(raw_breadth, window=z_window, min_frac=min_frac),
        disp_z=rolling_z(raw_disp, window=z_window, min_frac=min_frac),
        active_counts=active_counts,
    )

