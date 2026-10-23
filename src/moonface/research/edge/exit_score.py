# src/moonface/backtest/edge/exit_score.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from moonface.research.sizing import split_research_tail
from moonface.core.exits import ExitFn
from moonface.research.edge.signals import atr_channel_break, donchian_break, ma_cross
from moonface.core.metrics import Summary, summarize_r
from moonface.core.models import Candle

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]

# Entry sets per timeframe: the positive-drift winners from the edge probe on each
# timeframe. The "1h" set is the edge-probe finding; the "4h" set is derived from
# the H4 edge-probe leaderboard (top 3 by hzn exp with positive hzn OOS exp and
# hzn OOS n >= 30).
ENTRY_SPECS_BY_TF: dict[str, list[tuple[str, Generator, dict]]] = {
    "1h": [
        ("atr_channel_break", atr_channel_break, {"k": 2.0, "atr_period": 14}),
        ("ma_cross", ma_cross, {"fast": 50, "slow": 200}),
        ("donchian_break", donchian_break, {"n": 100}),
    ],
    "4h": [
        ("donchian_break", donchian_break, {"n": 100}),
        ("atr_channel_break", atr_channel_break, {"k": 1.5, "atr_period": 14}),
        ("donchian_break", donchian_break, {"n": 55}),
    ],
}


@dataclass(frozen=True)
class ExitRow:
    entry: str
    entry_params: dict
    exit: str
    exit_params: dict
    research_trades: int
    research_net_r: float
    research_expectancy_r: float
    research_max_dd_r: float
    oos_trades: int
    oos_net_r: float
    oos_expectancy_r: float
    valid: bool


def exit_gate(research: Summary, tail: Summary, min_trades: int = 30,
              max_drawdown_r: float = 15.0) -> bool:
    """Strict both-folds rule: research-positive AND OOS-positive AND enough OOS
    trades AND research drawdown within budget. summarize_r reports drawdown as a
    non-positive number, so a 15R budget means max_drawdown_r >= -15."""
    return (research.expectancy_r > 0.0
            and tail.expectancy_r > 0.0
            and tail.trade_count >= min_trades
            and research.max_drawdown_r >= -max_drawdown_r)


def score_exit(h1: list[Candle], entry_name: str, entry_params: dict,
               entries: list[tuple[int, str]], exit_name: str, exit_fn: ExitFn,
               exit_params: dict, tail_start: int) -> ExitRow:
    research: list[float] = []
    tail: list[float] = []
    for i, side in entries:
        r = exit_fn(i, side, h1, exit_params)
        if r is not None:
            (research if i < tail_start else tail).append(r)
    rs = summarize_r(research)
    ts = summarize_r(tail)
    return ExitRow(
        entry=entry_name, entry_params=entry_params,
        exit=exit_name, exit_params=exit_params,
        research_trades=rs.trade_count, research_net_r=rs.total_r,
        research_expectancy_r=rs.expectancy_r, research_max_dd_r=rs.max_drawdown_r,
        oos_trades=ts.trade_count, oos_net_r=ts.total_r,
        oos_expectancy_r=ts.expectancy_r,
        valid=exit_gate(rs, ts),
    )


def exit_r_streams(
    h1: list[Candle],
    entries: list[tuple[int, str]],
    exit_fn: ExitFn,
    exit_params: dict,
    tail_start: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Ordered (timestamp_ms, r_multiple) pairs split at tail_start. Same loop as
    score_exit, returning the streams instead of summarizing. None exits are dropped."""
    research: list[tuple[int, float]] = []
    tail: list[tuple[int, float]] = []
    for i, side in entries:
        r = exit_fn(i, side, h1, exit_params)
        if r is not None:
            pair = (h1[i].timestamp_ms, r)
            (research if i < tail_start else tail).append(pair)
    return research, tail


def run_exit_battery(h1: list[Candle], entry_specs: list[tuple[str, Generator, dict]],
                     exit_registry: dict[str, tuple], oos_tail_bars: int,
                     warmup: int, future_bars: int) -> list[ExitRow]:
    tail_start = split_research_tail(h1, oos_tail_bars, warmup, future_bars)
    rows: list[ExitRow] = []
    for entry_name, generator, entry_params in entry_specs:
        entries = generator(h1, entry_params)
        for exit_name, (exit_fn, grid) in exit_registry.items():
            for exit_params in grid:
                rows.append(score_exit(h1, entry_name, entry_params, entries,
                                       exit_name, exit_fn, exit_params, tail_start))
    return sorted(rows, key=lambda r: r.oos_expectancy_r, reverse=True)