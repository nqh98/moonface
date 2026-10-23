from __future__ import annotations

from moonface.core.models import Candle
from moonface.core.risk import atr


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    if period <= 0:
        return values[-1]
    alpha = 2.0 / (period + 1.0)
    out = values[0]
    for value in values[1:]:
        out = alpha * value + (1.0 - alpha) * out
    return out


def roc(values: list[float], n: int) -> float:
    if n <= 0 or len(values) <= n:
        return 0.0
    base = values[-n - 1]
    if base == 0:
        return 0.0
    return (values[-1] - base) / base


def sma(values: list[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    window = values[-period:]
    return sum(window) / len(window)


def stdev(values: list[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    window = values[-period:]
    if len(window) < 2:
        return 0.0
    mean = sum(window) / len(window)
    return (sum((value - mean) ** 2 for value in window) / len(window)) ** 0.5


def donchian_high(candles: list[Candle], n: int) -> float:
    if not candles:
        return 0.0
    if n <= 0:
        return 0.0
    window = candles[-(n + 1):-1] if len(candles) > n else candles[:-1]
    if not window:
        return candles[-1].high
    return max(candle.high for candle in window)


def donchian_low(candles: list[Candle], n: int) -> float:
    if not candles:
        return 0.0
    if n <= 0:
        return 0.0
    window = candles[-(n + 1):-1] if len(candles) > n else candles[:-1]
    if not window:
        return candles[-1].low
    return min(candle.low for candle in window)


def _true_range(current: Candle, previous_close: float) -> float:
    return max(
        current.high - current.low,
        abs(current.high - previous_close),
        abs(current.low - previous_close),
    )


def adx(candles: list[Candle], period: int) -> float:
    if period <= 0 or len(candles) < 2 * period + 1:
        return 0.0
    trs: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous = candles[index - 1]
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        trs.append(_true_range(current, previous.close))

    def _wilder(values: list[float], length: int) -> list[float]:
        if len(values) < length:
            return []
        acc = sum(values[:length])
        out = [acc]
        for value in values[length:]:
            acc = acc - acc / length + value
            out.append(acc)
        return out

    tr_s = _wilder(trs, period)
    pdm_s = _wilder(plus_dm, period)
    mdm_s = _wilder(minus_dm, period)
    dx: list[float] = []
    for tr_, pdm_, mdm_ in zip(tr_s, pdm_s, mdm_s):
        if tr_ == 0:
            dx.append(0.0)
            continue
        pdi = 100.0 * pdm_ / tr_
        mdi = 100.0 * mdm_ / tr_
        denom = pdi + mdi
        dx.append(0.0 if denom == 0 else 100.0 * abs(pdi - mdi) / denom)
    if len(dx) < period:
        return 0.0
    val = sum(dx[:period]) / period
    for d in dx[period:]:
        val = (val * (period - 1) + d) / period
    return val


def rsi(closes: list[float], period: int) -> float:
    if period <= 0 or len(closes) < period + 1:
        return 50.0

    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        delta = closes[index] - closes[index - 1]
        if delta > 0:
            gains += delta
        else:
            losses -= delta

    avg_gain = gains / period
    avg_loss = losses / period

    for index in range(period + 1, len(closes)):
        delta = closes[index] - closes[index - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def vol_ratio(candles: list[Candle], atr_period: int, baseline: int) -> float:
    if atr_period <= 0 or baseline <= 0:
        return 0.0
    baseline_atr = atr(candles, baseline)
    if baseline_atr <= 0:
        return 0.0
    current_atr = atr(candles, atr_period)
    return current_atr / baseline_atr
