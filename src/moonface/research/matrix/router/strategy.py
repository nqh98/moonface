from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.strategies import (
    DONCHIAN_N,
    BaselineTrade,
    _net,
    _signal,
)
from moonface.research.matrix.router.semantics import MODE_FREEZE, MODE_SIZE


def router_conditioned(
    candles: list[Candle],
    modes: dict[int, int],
    *,
    n: int = DONCHIAN_N,
    cost: CostModel | None = None,
    next_bar_open: bool = True,
) -> list[BaselineTrade]:
    cost = cost or CostModel()
    fill_off = 1 if next_bar_open else 0
    trades: list[BaselineTrade] = []
    side = 0
    size = 0.0
    e_i = e_ts = 0
    e_px = 0.0
    for i in range(n, len(candles)):
        mode = modes.get(i, MODE_FREEZE)
        desired = _signal(candles, i, n)
        if mode == MODE_FREEZE:
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
                        size * _net(side, e_px, px, cost),
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
                BaselineTrade(
                    side,
                    e_i,
                    e_ts,
                    e_px,
                    fi,
                    ts,
                    px,
                    size * _net(side, e_px, px, cost),
                )
            )
        side, size, e_i, e_ts, e_px = desired, MODE_SIZE[mode], fi, ts, px
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
                    size * _net(side, e_px, px, cost),
                )
            )
    return trades
