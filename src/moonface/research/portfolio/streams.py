"""Per-bar position + return series for portfolio components (1h grid)."""
from __future__ import annotations

from moonface.core.metrics import COST_FRACTION, resolve_trade_span
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap

_ATR_PERIOD = 14


def asset_bar_r(candles: list[Candle], period: int = _ATR_PERIOD) -> list[float]:
    """Common portfolio currency: per-bar return in 1*ATR(bar) units."""
    out = [0.0]
    for t in range(1, len(candles)):
        a = atr(candles[:t + 1], period)
        if not a or a <= 0:
            out.append(0.0)
            continue
        out.append((candles[t].close - candles[t - 1].close) / a)
    return out


def native_positions(candles: list[Candle], cell) -> list[float]:
    """Per-bar target position (+-1/0) for a component on its NATIVE timeframe."""
    events = nonoverlap(
        PRICE_FAMILIES[cell.family](candles, cell.params), cell.h,
    )
    pos = [0.0] * len(candles)
    for i, side in events:
        span = resolve_trade_span(
            candles, i, side, cell.exit_name, cell.exit_params,
        )
        if span is None:
            continue
        _, exit_idx, _, _ = span
        sign = 1.0 if side == "LONG" else -1.0
        for t in range(i + 1, min(exit_idx, len(candles) - 1) + 1):
            pos[t] = sign
    return pos


def align_to_grid(
    native_pos: list[float],
    native_candles: list[Candle],
    grid_candles: list[Candle],
) -> list[float]:
    """Forward-fill native positions onto a finer grid by timestamp (lookahead-free)."""
    out: list[float] = []
    j = 0
    for gc in grid_candles:
        while j + 1 < len(native_candles) and \
                native_candles[j + 1].timestamp_ms <= gc.timestamp_ms:
            j += 1
        out.append(native_pos[j] if native_pos else 0.0)
    return out


def component_positions(
    native_by_tf: dict,
    cell,
    grid_candles: list[Candle],
) -> list[float]:
    """Native positions for cell.timeframe, aligned onto grid_candles (1h)."""
    candles = native_by_tf[cell.timeframe]
    return align_to_grid(native_positions(candles, cell), candles, grid_candles)


def position_returns(
    positions: list[float],
    asset_bar_r_grid: list[float],
    grid_candles: list[Candle],
    atr_period: int = _ATR_PERIOD,
) -> list[float]:
    """Per-bar P&L in the common currency: position * asset_bar_r - turnover cost.

    Cost is one-way: |Δposition| * COST_FRACTION / (2 * atr_frac), so an entry+exit
    round-trip costs COST_FRACTION/atr_frac — matching single_trade_r's per-trade cost."""
    out = [0.0] * len(positions)
    prev = 0.0
    for t in range(len(positions)):
        gross = positions[t] * asset_bar_r_grid[t]
        cost = 0.0
        if positions[t] != prev:
            a = atr(grid_candles[:t + 1], atr_period)
            if a and a > 0:
                atr_frac = a / grid_candles[t].close
                cost = abs(positions[t] - prev) * COST_FRACTION / (2.0 * atr_frac)
        out[t] = gross - cost
        prev = positions[t]
    return out
