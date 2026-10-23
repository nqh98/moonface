"""Donchian breakout + trailing-stop trend simulator (deployment-oriented).

Separate from backtest/engine.py (which is frozen): the shared engine resolves
fixed-TP brackets; this module trails a stop with the channel and accrues
funding. It is simultaneously the Stage-1 audit reference and the Stage-3
Donchian strategy engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from moonface.core.models import Candle
from moonface.core.risk import atr as _atr

Side = Literal["BUY", "SELL"]


def donchian_prior(candles: list[Candle], i: int, n: int) -> tuple[float, float]:
    """(high, low) of the n bars ending immediately before index i (bars [i-n, i)).

    Excludes the current bar so a breakout is measured against realised history
    only (no lookahead). Returns (0, 0) for insufficient history.
    """
    if i < n or n <= 0:
        return (0.0, 0.0)
    window = candles[i - n:i]
    return (max(c.high for c in window), min(c.low for c in window))


def detect_breakouts(
    candles: list[Candle], n: int, long_only: bool = True
) -> list[tuple[int, Side]]:
    """Bar indices where close breaks the prior-n channel, with side.

    Long breakout: candles[i].close > prior high. Short (if allowed):
    candles[i].close < prior low. One signal per bar; ordered ascending.
    """
    out: list[tuple[int, Side]] = []
    for i in range(n, len(candles)):
        hi, lo = donchian_prior(candles, i, n)
        if candles[i].close > hi:
            out.append((i, "BUY"))
        elif not long_only and candles[i].close < lo:
            out.append((i, "SELL"))
    return out


@dataclass(frozen=True)
class TrendParams:
    entry_n: int = 20
    trail_n: int = 10
    atr_period: int = 14
    k_stop: float = 2.0
    long_only: bool = True
    fee_rate: float = 0.00045
    slippage: float = 0.0005
    funding_enabled: bool = True
    exit_mode: str = "trail"        # "trail" | "stop_only" | "fixed_horizon"
    fh_bars: int = 12               # time-exit horizon for fixed_horizon
    next_bar_open: bool = False     # fill entry/exit at next bar's open
    stop_extra_slip: float = 0.0    # extra slippage applied only on stop exits


@dataclass(frozen=True)
class TrendTrade:
    side: Side
    entry_index: int
    entry: float
    exit_index: int
    exit: float
    r_multiple: float
    mae_r: float
    hold_bars: int
    funding_paid_r: float = 0.0


def simulate_donchian(
    candles: list[Candle], params: TrendParams, funding_points=None
) -> list[TrendTrade]:
    """Vectorized Donchian breakout + trailing-stop simulator.

    Entry: on the first bar after a breakout (close beyond prior entry_n channel).
    Initial stop: entry -/+ k_stop*ATR (ATR over atr_period). The stop is then
    trailed by the prior trail_n channel extreme (ratcheted toward price only —
    a long's stop only ever moves up). Exit when a bar's range touches the stop.
    Only one position open at a time; the next entry can only occur after exit.
    r_multiple is net of fees + slippage (+ funding when enabled, Task 5).
    """
    trades: list[TrendTrade] = []
    n = len(candles)
    i = params.entry_n
    while i < n:
        side = _breakout_side(candles, i, params)
        if side is None:
            i += 1
            continue
        if params.next_bar_open:
            if i + 1 >= n:
                break
            entry_idx, entry = i + 1, candles[i + 1].open
        else:
            entry_idx, entry = i, candles[i].close
        a = _atr(candles[: entry_idx + 1], params.atr_period)
        if a <= 0:
            i += 1
            continue
        stop0 = entry - params.k_stop * a if side == "BUY" else entry + params.k_stop * a
        trade = _run_position(candles, entry_idx, side, entry, stop0, params, funding_points)
        if trade is not None:
            trades.append(trade)
            i = trade.exit_index + 1
        else:
            i += 1
    return trades


def _breakout_side(candles, i, params):
    hi, lo = donchian_prior(candles, i, params.entry_n)
    if candles[i].close > hi:
        return "BUY"
    if not params.long_only and candles[i].close < lo:
        return "SELL"
    return None


def _run_position(candles, entry_idx, side, entry, stop0, params, funding_points):
    risk = (entry - stop0) if side == "BUY" else (stop0 - entry)
    if risk <= 0:
        return None
    trail_stop = stop0
    mae = 0.0
    for j in range(entry_idx + 1, len(candles)):
        c = candles[j]
        if params.exit_mode == "trail":
            hi, lo = donchian_prior(candles, j, params.trail_n)
            trail_stop = max(trail_stop, lo) if side == "BUY" else min(trail_stop, hi)
        if side == "BUY":
            mae = max(mae, (entry - c.low) / risk)
            if c.low <= trail_stop:
                return _close_trade(candles, side, entry_idx, entry, j, trail_stop,
                                    risk, mae, params, funding_points, is_stop_exit=True)
        else:
            mae = max(mae, (c.high - entry) / risk)
            if c.high >= trail_stop:
                return _close_trade(candles, side, entry_idx, entry, j, trail_stop,
                                    risk, mae, params, funding_points, is_stop_exit=True)
        if params.exit_mode == "fixed_horizon" and (j - entry_idx) >= params.fh_bars:
            return _close_trade(candles, side, entry_idx, entry, j, c.close,
                                risk, mae, params, funding_points, is_stop_exit=False)
    last = len(candles) - 1
    return _close_trade(candles, side, entry_idx, entry, last, candles[last].close,
                        risk, mae, params, funding_points, is_stop_exit=False)


def _funding_r_for_trade(candles, side, entry_idx, exit_idx, risk, notional,
                         funding_points):
    from moonface.research.funding_cost import held_funding_rates, funding_cost_r
    entry_ms = candles[entry_idx].timestamp_ms
    exit_ms = candles[exit_idx].timestamp_ms
    held = held_funding_rates(funding_points, entry_ms, exit_ms)
    return funding_cost_r(held, side, risk, notional)


def _close_trade(candles, side, entry_idx, entry, exit_idx, raw_exit, risk,
                 mae, params, funding_points, is_stop_exit=False):
    if params.next_bar_open and exit_idx + 1 < len(candles):
        raw_exit = candles[exit_idx + 1].open
        exit_idx_eff = exit_idx + 1
    else:
        exit_idx_eff = exit_idx
    slip = params.slippage + (params.stop_extra_slip if is_stop_exit else 0.0)
    exit_slip = raw_exit * slip
    entry_slip = entry * params.slippage
    exit_price = (raw_exit - exit_slip) if side == "BUY" else (raw_exit + exit_slip)
    fill_entry = entry + entry_slip if side == "BUY" else entry - entry_slip
    pnl = (exit_price - fill_entry) if side == "BUY" else (fill_entry - exit_price)
    fees = params.fee_rate * (fill_entry + exit_price)
    funding_r = 0.0
    if params.funding_enabled and funding_points:
        funding_r = _funding_r_for_trade(candles, side, entry_idx, exit_idx_eff,
                                         risk, fill_entry, funding_points)
    r = round((pnl - fees) / risk - funding_r, 4)
    return TrendTrade(side=side, entry_index=entry_idx, entry=round(fill_entry, 6),
                      exit_index=exit_idx_eff, exit=round(exit_price, 6),
                      r_multiple=r, mae_r=round(mae, 4),
                      hold_bars=exit_idx_eff - entry_idx, funding_paid_r=round(funding_r, 6))
