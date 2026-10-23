from __future__ import annotations

from dataclasses import dataclass
import math

from moonface.core.models import Candle
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.trend_sim import donchian_prior

DONCHIAN_N = 20
ATR_PERIOD = 14
FREEZE_PCTL = 0.80
FREEZE_LOOKBACK = 500


@dataclass(frozen=True)
class BaselineTrade:
    side: int
    entry_index: int
    entry_ts_ms: int
    entry_px: float
    exit_index: int
    exit_ts_ms: int
    exit_px: float
    net_return: float


def _signal(candles: list[Candle], i: int, n: int) -> int:
    hi, lo = donchian_prior(candles, i, n)
    if hi <= 0.0:
        return 0
    if candles[i].close > hi:
        return 1
    if candles[i].close < lo:
        return -1
    return 0


def _net(side: int, entry_px: float, exit_px: float, cost: CostModel) -> float:
    return side * (exit_px - entry_px) / entry_px - cost.round_trip()


def donchian_reverse(
    candles: list[Candle],
    *,
    n: int = DONCHIAN_N,
    cost: CostModel | None = None,
    next_bar_open: bool = True,
) -> list[BaselineTrade]:
    cost = cost or CostModel()
    fill_off = 1 if next_bar_open else 0
    trades: list[BaselineTrade] = []
    side = 0
    e_i = e_ts = 0
    e_px = 0.0
    for i in range(n, len(candles)):
        desired = _signal(candles, i, n)
        if desired == 0 or desired == side:
            continue
        fi = i + fill_off
        if fi >= len(candles):
            break
        px = candles[fi].open if next_bar_open else candles[i].close
        ts = candles[fi].timestamp_ms
        if side != 0:
            trades.append(
                BaselineTrade(side, e_i, e_ts, e_px, fi, ts, px, _net(side, e_px, px, cost))
            )
        side, e_i, e_ts, e_px = desired, fi, ts, px
    if side != 0:
        last = len(candles) - 1
        if last > e_i:
            px = candles[last].close
            trades.append(
                BaselineTrade(
                    side,
                    e_i,
                    e_ts,
                    e_px,
                    last,
                    candles[last].timestamp_ms,
                    px,
                    _net(side, e_px, px, cost),
                )
            )
    return trades


def _true_range(candles: list[Candle], i: int) -> float:
    if i == 0:
        return candles[0].high - candles[0].low
    prev_close = candles[i - 1].close
    return max(
        candles[i].high - candles[i].low,
        abs(candles[i].high - prev_close),
        abs(candles[i].low - prev_close),
    )


def _atr_series(candles: list[Candle], period: int) -> list[float]:
    tr = [_true_range(candles, i) for i in range(len(candles))]
    out: list[float] = []
    for i in range(len(candles)):
        lo = max(0, i - period + 1)
        win = tr[lo : i + 1]
        out.append(sum(win) / len(win))
    return out


def _percentile(sorted_vals: list[float], pctl: float) -> float:
    k = math.ceil(pctl * len(sorted_vals))
    k = min(max(k, 1), len(sorted_vals))
    return sorted_vals[k - 1]


def _freeze_flags(atr_series: list[float], pctl: float, lookback: int) -> list[bool]:
    flags = [False] * len(atr_series)
    for i in range(len(atr_series)):
        if i + 1 < lookback:
            continue
        window = sorted(atr_series[i - lookback + 1 : i + 1])
        flags[i] = atr_series[i] > _percentile(window, pctl)
    return flags


def donchian_reverse_frozen(
    candles: list[Candle],
    *,
    n: int = DONCHIAN_N,
    atr_period: int = ATR_PERIOD,
    freeze_pctl: float = FREEZE_PCTL,
    freeze_lookback: int = FREEZE_LOOKBACK,
    cost: CostModel | None = None,
    next_bar_open: bool = True,
) -> list[BaselineTrade]:
    cost = cost or CostModel()
    frozen = _freeze_flags(_atr_series(candles, atr_period), freeze_pctl, freeze_lookback)
    fill_off = 1 if next_bar_open else 0
    trades: list[BaselineTrade] = []
    side = 0
    e_i = e_ts = 0
    e_px = 0.0
    for i in range(n, len(candles)):
        desired = _signal(candles, i, n)
        if frozen[i]:
            if side != 0 and desired != 0 and desired != side:
                fi = i + fill_off
                if fi >= len(candles):
                    break
                px = candles[fi].open if next_bar_open else candles[i].close
                trades.append(
                    BaselineTrade(
                        side,
                        e_i,
                        e_ts,
                        e_px,
                        fi,
                        candles[fi].timestamp_ms,
                        px,
                        _net(side, e_px, px, cost),
                    )
                )
                side = 0
            continue
        if desired == 0 or desired == side:
            continue
        fi = i + fill_off
        if fi >= len(candles):
            break
        px = candles[fi].open if next_bar_open else candles[i].close
        ts = candles[fi].timestamp_ms
        if side != 0:
            trades.append(
                BaselineTrade(side, e_i, e_ts, e_px, fi, ts, px, _net(side, e_px, px, cost))
            )
        side, e_i, e_ts, e_px = desired, fi, ts, px
    if side != 0:
        last = len(candles) - 1
        if last > e_i:
            px = candles[last].close
            trades.append(
                BaselineTrade(
                    side,
                    e_i,
                    e_ts,
                    e_px,
                    last,
                    candles[last].timestamp_ms,
                    px,
                    _net(side, e_px, px, cost),
                )
            )
    return trades
