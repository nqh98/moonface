from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import ActionPlan, Candle
from moonface.core.risk import risk_reward

# Limit fill outcomes:
#   TP1     filled, first target banked (also covers a stop-out after TP1)
#   TP2     filled, second target reached
#   SL      filled, stopped before any target
#   NO_FILL entry price never traded; no position taken
#   OPEN    filled but unresolved at the end of the data window
Outcome = str


@dataclass(frozen=True)
class Trade:
    side: str
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr1: float
    rr2: float
    outcome: Outcome
    r_multiple: float | None
    entry_index: int = 0
    timestamp_ms: int = 0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    bars_to_fill: int = 0
    bars_to_resolve: int = 0


def simulate_trade(
    plan: ActionPlan,
    future: list[Candle],
    fee_rate: float = 0.0,
    slippage: float = 0.0,
    *,
    entry_index: int = 0,
    timestamp_ms: int = 0,
) -> Trade | None:
    """Simulate one limit-entry trade.

    The position fills only when a future bar trades through ``plan.entry``;
    otherwise the result is ``NO_FILL``. Once filled, bars that touch both a
    stop and a target are resolved stop-first (conservative). After TP1 trades,
    the trade is treated as a win of at least ``rr1``. Realised R is net of fees
    and slippage.
    """
    if not future:
        return None
    rr1, rr2 = risk_reward(plan)
    if plan.side == "BUY":
        entry = plan.entry + slippage
        risk = entry - plan.stop_loss
    else:
        entry = plan.entry - slippage
        risk = plan.stop_loss - entry
    if risk <= 0:
        return None

    fill_offset = next(
        (i for i, c in enumerate(future) if c.low <= plan.entry <= c.high), None
    )
    if fill_offset is None:
        return _trade(plan, entry, rr1, rr2, "NO_FILL", None, entry_index, timestamp_ms)

    state = {"mfe": 0.0, "mae": 0.0}

    def track(c: Candle) -> None:
        if plan.side == "BUY":
            fav, adv = (c.high - entry) / risk, (entry - c.low) / risk
        else:
            fav, adv = (entry - c.low) / risk, (c.high - entry) / risk
        state["mfe"] = max(state["mfe"], fav)
        state["mae"] = max(state["mae"], adv)

    def resolved(outcome: str, target: float, offset: int) -> Trade:
        exit_price = target - slippage if plan.side == "BUY" else target + slippage
        return _close(
            plan, entry, exit_price, risk, outcome, fee_rate, rr1, rr2,
            entry_index + offset, timestamp_ms,
            mfe_r=round(state["mfe"], 4), mae_r=round(state["mae"], 4),
            bars_to_fill=fill_offset, bars_to_resolve=offset - fill_offset,
        )

    tp1_hit = False
    for offset in range(fill_offset, len(future)):
        c = future[offset]
        track(c)
        if plan.side == "BUY":
            hit_stop = c.low <= plan.stop_loss
            hit_tp1 = c.high >= plan.take_profit_1
            hit_tp2 = c.high >= plan.take_profit_2
        else:
            hit_stop = c.high >= plan.stop_loss
            hit_tp1 = c.low <= plan.take_profit_1
            hit_tp2 = c.low <= plan.take_profit_2
        if not tp1_hit:
            if hit_stop:
                return resolved("SL", plan.stop_loss, offset)
            if hit_tp2:
                return resolved("TP2", plan.take_profit_2, offset)
            if hit_tp1:
                tp1_hit = True
        else:
            if hit_tp2:
                return resolved("TP2", plan.take_profit_2, offset)
            if hit_stop:
                return resolved("TP1", plan.take_profit_1, offset)

    last_offset = len(future) - 1
    if tp1_hit:
        return resolved("TP1", plan.take_profit_1, last_offset)
    return _close(
        plan, entry, future[-1].close, risk, "OPEN", fee_rate, rr1, rr2,
        entry_index + last_offset, timestamp_ms,
        mfe_r=round(state["mfe"], 4), mae_r=round(state["mae"], 4),
        bars_to_fill=fill_offset, bars_to_resolve=last_offset - fill_offset,
    )


def _close(
    plan: ActionPlan,
    entry: float,
    exit_price: float,
    risk: float,
    outcome: Outcome,
    fee_rate: float,
    rr1: float,
    rr2: float,
    index: int,
    timestamp_ms: int,
    *,
    mfe_r: float = 0.0,
    mae_r: float = 0.0,
    bars_to_fill: int = 0,
    bars_to_resolve: int = 0,
) -> Trade:
    pnl = exit_price - entry if plan.side == "BUY" else entry - exit_price
    fees = fee_rate * (entry + exit_price)
    r_multiple = round((pnl - fees) / risk, 4)
    return _trade(plan, entry, rr1, rr2, outcome, r_multiple, index, timestamp_ms,
                  mfe_r=mfe_r, mae_r=mae_r, bars_to_fill=bars_to_fill,
                  bars_to_resolve=bars_to_resolve)


def _trade(
    plan: ActionPlan,
    entry: float,
    rr1: float,
    rr2: float,
    outcome: Outcome,
    r_multiple: float | None,
    index: int,
    timestamp_ms: int,
    *,
    mfe_r: float = 0.0,
    mae_r: float = 0.0,
    bars_to_fill: int = 0,
    bars_to_resolve: int = 0,
) -> Trade:
    return Trade(
        side=plan.side,
        entry=entry,
        stop_loss=plan.stop_loss,
        take_profit_1=plan.take_profit_1,
        take_profit_2=plan.take_profit_2,
        rr1=rr1,
        rr2=rr2,
        outcome=outcome,
        r_multiple=r_multiple,
        entry_index=index,
        timestamp_ms=timestamp_ms,
        mfe_r=mfe_r,
        mae_r=mae_r,
        bars_to_fill=bars_to_fill,
        bars_to_resolve=bars_to_resolve,
    )


def simulate_market_entry(
    plan: ActionPlan,
    future: list[Candle],
    fee_rate: float = 0.0,
    slippage: float = 0.0,
    *,
    entry_index: int = 0,
    timestamp_ms: int = 0,
) -> Trade | None:
    """Counterfactual: enter at the first future bar's open instead of a limit.

    Used only by diagnostics to estimate what a NO_FILL setup would have done.
    Resolution logic mirrors ``simulate_trade`` (stop-first on ambiguous bars).
    """
    if not future:
        return None
    market = ActionPlan(
        side=plan.side, bias=plan.bias, entry=future[0].open,
        stop_loss=plan.stop_loss, take_profit_1=plan.take_profit_1,
        take_profit_2=plan.take_profit_2, risk_percentage=plan.risk_percentage,
        source_timeframe=plan.source_timeframe,
    )
    # Force a fill on bar 0 by treating the open as the entry trigger.
    forced = [Candle(future[0].timestamp_ms, future[0].open, future[0].high,
                     future[0].low, future[0].close, future[0].volume), *future[1:]]
    return simulate_trade(market, forced, fee_rate, slippage,
                          entry_index=entry_index, timestamp_ms=timestamp_ms)
