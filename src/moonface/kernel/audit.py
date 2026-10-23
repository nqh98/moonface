"""Stage-1 audit: reconcile the shared engine and sweep cost sensitivity.

We do NOT modify backtest/engine.py. Instead we independently re-derive the
per-trade R of fixed-TP Donchian breakout brackets and diff against
simulate_trade, proving the engine's fill/fee/R math is correct. Funding and
trailing-stop are NEW capabilities (Tasks 4-5) audited by their own unit tests.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.features.simulate import simulate_trade
from moonface.research.trend_sim import detect_breakouts
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.core.metrics import summarize_r
from moonface.core.models import ActionPlan, Candle


def fixed_tp_plans_from_breakouts(
    candles: list[Candle], n: int, rr1: float, rr2: float
) -> list[tuple[int, ActionPlan]]:
    """Build fixed-RR BUY/SELL brackets at each breakout bar, for engine recon.

    stop = opposing channel extreme; targets = entry +/- RR*risk. This is the
    fixed-TP shape the engine understands (no trailing, no funding).
    """
    from moonface.research.trend_sim import donchian_prior

    plans: list[tuple[int, ActionPlan]] = []
    for i, side in detect_breakouts(candles, n, long_only=False):
        hi, lo = donchian_prior(candles, i, n)
        entry = candles[i].close
        if side == "BUY":
            stop = lo
            risk = entry - stop
            if risk <= 0:
                continue
            plans.append((i, ActionPlan(
                side="BUY", bias="LONG", entry=entry, stop_loss=stop,
                take_profit_1=entry + rr1 * risk, take_profit_2=entry + rr2 * risk,
                risk_percentage=0.0, source_timeframe="audit")))
        else:
            stop = hi
            risk = stop - entry
            if risk <= 0:
                continue
            plans.append((i, ActionPlan(
                side="SELL", bias="SHORT", entry=entry, stop_loss=stop,
                take_profit_1=entry - rr1 * risk, take_profit_2=entry - rr2 * risk,
                risk_percentage=0.0, source_timeframe="audit")))
    return plans


@dataclass(frozen=True)
class Reconciliation:
    max_abs_r_diff: float
    n_trades: int


def _independent_r(plan: ActionPlan, future: list[Candle],
                   fee_rate: float, slippage: float) -> float | None:
    """Naive re-derivation of one bracket's R, mirroring engine semantics:
    first bar whose range touches entry fills; SL is stop-first vs TP; once TP1
    is banked the trade resolves TP2 or TP1-on-stop. Returns None on NO_FILL.

    Two engine subtleties this MUST replicate to match to 1e-6 (validated):
      * end-of-window with TP1 banked resolves TP1 @ take_profit_1 (resolved
        exit); otherwise OPEN at the last close;
      * exit slippage is applied to RESOLVED exits (SL/TP1/TP2) but NOT to the
        OPEN-at-window-end exit.
    """
    entry = plan.entry + slippage if plan.side == "BUY" else plan.entry - slippage
    risk = (entry - plan.stop_loss) if plan.side == "BUY" else (plan.stop_loss - entry)
    if risk <= 0:
        return None
    fill = next((k for k, c in enumerate(future)
                 if c.low <= plan.entry <= c.high), None)
    if fill is None:
        return None
    seq = future[fill:]
    buy = plan.side == "BUY"

    def finalize(raw_exit: float, apply_slip: bool) -> float:
        ep = ((raw_exit - slippage) if buy else (raw_exit + slippage)) if apply_slip else raw_exit
        pnl = (ep - entry) if buy else (entry - ep)
        fees = fee_rate * (entry + ep)
        return round((pnl - fees) / risk, 4)

    tp1_hit = False
    for c in seq:
        if buy:
            hit_stop = c.low <= plan.stop_loss
            hit_tp1 = c.high >= plan.take_profit_1
            hit_tp2 = c.high >= plan.take_profit_2
        else:
            hit_stop = c.high >= plan.stop_loss
            hit_tp1 = c.low <= plan.take_profit_1
            hit_tp2 = c.low <= plan.take_profit_2
        if not tp1_hit:
            if hit_stop:
                return finalize(plan.stop_loss, True)
            if hit_tp2:
                return finalize(plan.take_profit_2, True)
            if hit_tp1:
                tp1_hit = True
        else:
            if hit_tp2:
                return finalize(plan.take_profit_2, True)
            if hit_stop:
                return finalize(plan.take_profit_1, True)
    # end of window: TP1 banked -> resolved TP1 (slippage); else OPEN (no slippage)
    if tp1_hit:
        return finalize(plan.take_profit_1, True)
    return finalize(seq[-1].close, False)


def reconcile_vs_engine(candles: list[Candle], n: int,
                        fee_rate: float, slippage: float) -> Reconciliation:
    plans = fixed_tp_plans_from_breakouts(candles, n, rr1=1.0, rr2=2.0)
    diffs: list[float] = []
    for idx, plan in plans:
        # future includes the signal bar so the limit fills at the breakout close
        # (the engine is a limit simulator; a breakout close gaps away in a trend,
        # so idx+1 would yield NO_FILL for almost every plan).
        future = candles[idx:]
        engine_trade = simulate_trade(
            plan, future, fee_rate=fee_rate, slippage=slippage, entry_index=idx)
        indep = _independent_r(plan, future, fee_rate, slippage)
        if engine_trade is None or engine_trade.r_multiple is None or indep is None:
            continue
        diffs.append(abs(engine_trade.r_multiple - indep))
    return Reconciliation(
        max_abs_r_diff=max(diffs) if diffs else 0.0, n_trades=len(diffs))


@dataclass(frozen=True)
class CostRow:
    fee: float
    slippage: float
    expectancy_r: float
    profit_factor: float
    mar: float


def _mar_of(rs: list[float]) -> float:
    """R-based MAR = |total_R| / |max_dd_R| (f-independent; equals |% return|/|max_dd %|)."""
    total = sum(rs)
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    if max_dd == 0:
        return 0.0
    return round(abs(total) / abs(max_dd), 4)


def cost_sweep(candles, funding_points, params: TrendParams,
               fee_grid: list[float], slip_grid: list[float]) -> list[CostRow]:
    """Net expectancy / PF / MAR across a fee x slippage grid.

    Holding the strategy fixed, rising cost can only lower expectancy — this
    makes the cost cliff visible (the failure mode of the prior book-depth study).
    """
    rows: list[CostRow] = []
    for fee in fee_grid:
        for slip in slip_grid:
            p = TrendParams(**{**params.__dict__,
                               "fee_rate": fee, "slippage": slip})
            trades = simulate_donchian(candles, p, funding_points)
            rs = [t.r_multiple for t in trades]
            s = summarize_r(rs)
            rows.append(CostRow(fee, slip, s.expectancy_r, s.profit_factor, _mar_of(rs)))
    return rows
