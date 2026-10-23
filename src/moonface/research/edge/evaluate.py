from __future__ import annotations

from moonface.features.simulate import simulate_market_entry
from moonface.core.models import ActionPlan, Candle
from moonface.core.risk import atr, horizon_r, risk_unit  # noqa: F401

# Back-compat alias for callers that still import the private name.
_risk = risk_unit


def bracket_r(i: int, side: str, h1: list[Candle], k: float, m: float,
              atr_period: int, fee_rate: float, slippage: float) -> float | None:
    """ATR-bracket R: market-enter at the next bar's open, stop k*ATR, TP m*ATR."""
    risk = _risk(h1, i, k, atr_period)
    if risk is None:
        return None
    entry = h1[i].close
    if side == "LONG":
        plan = ActionPlan(side="BUY", bias="LONG", entry=entry,
                          stop_loss=entry - risk, take_profit_1=entry + m / k * risk,
                          take_profit_2=entry + m / k * risk, risk_percentage=1.0,
                          source_timeframe="H1")
    else:
        plan = ActionPlan(side="SELL", bias="SHORT", entry=entry,
                          stop_loss=entry + risk, take_profit_1=entry - m / k * risk,
                          take_profit_2=entry - m / k * risk, risk_percentage=1.0,
                          source_timeframe="H1")
    trade = simulate_market_entry(plan, h1[i + 1:], fee_rate, slippage,
                                  entry_index=i, timestamp_ms=h1[i].timestamp_ms)
    if trade is None or trade.r_multiple is None:
        return None
    return trade.r_multiple
