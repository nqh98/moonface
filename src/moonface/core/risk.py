from __future__ import annotations

from moonface.core.models import ActionPlan, Candle


def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    ranges: list[float] = []
    window = candles[-period:]
    for offset, current in enumerate(window):
        absolute_index = len(candles) - len(window) + offset
        previous_close = candles[absolute_index - 1].close if absolute_index > 0 else current.close
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous_close),
                abs(current.low - previous_close),
            )
        )
    return sum(ranges) / len(ranges)


def valid_buy_plan(plan: ActionPlan) -> bool:
    return plan.stop_loss < plan.entry < plan.take_profit_1 <= plan.take_profit_2


def valid_sell_plan(plan: ActionPlan) -> bool:
    return plan.take_profit_2 <= plan.take_profit_1 < plan.entry < plan.stop_loss


def risk_reward(plan: ActionPlan) -> tuple[float, float]:
    if plan.side == "BUY":
        risk = plan.entry - plan.stop_loss
        reward_1 = plan.take_profit_1 - plan.entry
        reward_2 = plan.take_profit_2 - plan.entry
    else:
        risk = plan.stop_loss - plan.entry
        reward_1 = plan.entry - plan.take_profit_1
        reward_2 = plan.entry - plan.take_profit_2
    if risk <= 0:
        return (0.0, 0.0)
    return (round(reward_1 / risk, 2), round(reward_2 / risk, 2))


def risk_unit(h1: list[Candle], i: int, k: float, atr_period: int) -> float | None:
    """k*ATR risk unit at bar i, or None if undefined (was edge.evaluate._risk)."""
    if i + 1 >= len(h1):
        return None
    a = atr(h1[: i + 1], atr_period)
    if a <= 0:
        return None
    return k * a


def horizon_r(i: int, side: str, h1: list[Candle], k: float,
              atr_period: int, n_bars: int) -> float | None:
    """Fixed-horizon R: signed forward return over n_bars, in k*ATR risk units."""
    risk = risk_unit(h1, i, k, atr_period)
    if risk is None:
        return None
    j = min(i + n_bars, len(h1) - 1)
    move = h1[j].close - h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    return round(sign * move / risk, 4)
