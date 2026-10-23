from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from moonface.research.edge.evaluate import bracket_r, horizon_r
from moonface.research.sizing import gated_score, split_research_tail
from moonface.core.metrics import summarize_r
from moonface.core.models import Candle

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]


@dataclass(frozen=True)
class ProbeRow:
    signal: str
    params: dict
    bracket_trades: int
    bracket_net_r: float
    bracket_expectancy_r: float
    bracket_win_rate: float
    bracket_valid: bool
    bracket_oos_net_r: float
    bracket_oos_trades: int
    horizon_trades: int
    horizon_expectancy_r: float
    horizon_win_rate: float
    horizon_oos_expectancy_r: float
    horizon_oos_trades: int


def score_signal(
    h1: list[Candle],
    name: str,
    generator: Generator,
    params: dict,
    k: float,
    m: float,
    n_bars: int,
    atr_period: int,
    fee_rate: float,
    slippage: float,
    oos_tail_bars: int,
    warmup: int,
    future_bars: int,
    min_trades: int = 30,
    max_drawdown_r: float = 15.0,
) -> ProbeRow:
    tail_start = split_research_tail(h1, oos_tail_bars, warmup, future_bars)
    entries = generator(h1, params)

    research_bracket: list[float] = []
    tail_bracket: list[float] = []
    research_horizon: list[float] = []
    tail_horizon: list[float] = []
    for i, side in entries:
        b = bracket_r(i, side, h1, k, m, atr_period, fee_rate, slippage)
        if b is not None:
            (research_bracket if i < tail_start else tail_bracket).append(b)
        hzn = horizon_r(i, side, h1, k, atr_period, n_bars)
        if hzn is not None:
            (research_horizon if i < tail_start else tail_horizon).append(hzn)

    research_summary = summarize_r(research_bracket)
    tail_summary = summarize_r(tail_bracket)
    score = gated_score(research_summary, tail_summary, min_trades, max_drawdown_r)
    horizon_summary = summarize_r(research_horizon)
    horizon_oos_summary = summarize_r(tail_horizon)

    return ProbeRow(
        signal=name,
        params=params,
        bracket_trades=research_summary.trade_count,
        bracket_net_r=research_summary.total_r,
        bracket_expectancy_r=research_summary.expectancy_r,
        bracket_win_rate=research_summary.win_rate,
        bracket_valid=score.valid,
        bracket_oos_net_r=score.oos_net_r,
        bracket_oos_trades=score.oos_trade_count,
        horizon_trades=horizon_summary.trade_count,
        horizon_expectancy_r=horizon_summary.expectancy_r,
        horizon_win_rate=horizon_summary.win_rate,
        horizon_oos_expectancy_r=horizon_oos_summary.expectancy_r,
        horizon_oos_trades=horizon_oos_summary.trade_count,
    )


def run_probe_battery(
    h1: list[Candle],
    registry: dict[str, tuple],
    k: float,
    m: float,
    n_bars: int,
    atr_period: int,
    fee_rate: float,
    slippage: float,
    oos_tail_bars: int,
    warmup: int,
    future_bars: int,
    min_trades: int = 30,
    max_drawdown_r: float = 15.0,
) -> list[ProbeRow]:
    rows: list[ProbeRow] = []
    for name, (generator, grid) in registry.items():
        for params in grid:
            rows.append(score_signal(
                h1, name, generator, params, k, m, n_bars, atr_period,
                fee_rate, slippage, oos_tail_bars, warmup, future_bars,
                min_trades, max_drawdown_r,
            ))
    return sorted(rows, key=lambda r: r.bracket_expectancy_r, reverse=True)
