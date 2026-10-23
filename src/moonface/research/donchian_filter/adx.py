from __future__ import annotations

from typing import Any

Candle = Any


def adx_series(candles: list[Candle], period: int = 14) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")

    n = len(candles)
    if n == 0:
        return []

    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    closes = [float(c.close) for c in candles]

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        if up_move > down_move and up_move > 0.0:
            plus_dm[i] = up_move
        elif down_move > up_move and down_move > 0.0:
            minus_dm[i] = down_move

        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    adx = [0.0] * n
    first_dx_index = period
    first_adx_index = 2 * period - 1
    if n <= first_adx_index:
        return adx

    atr = sum(tr[1 : period + 1])
    plus_smoothed = sum(plus_dm[1 : period + 1])
    minus_smoothed = sum(minus_dm[1 : period + 1])

    dx = [0.0] * n
    for i in range(first_dx_index, n):
        if i > first_dx_index:
            atr = atr - (atr / period) + tr[i]
            plus_smoothed = plus_smoothed - (plus_smoothed / period) + plus_dm[i]
            minus_smoothed = minus_smoothed - (minus_smoothed / period) + minus_dm[i]

        if atr == 0.0:
            dx[i] = 0.0
            continue

        plus_di = 100.0 * (plus_smoothed / atr)
        minus_di = 100.0 * (minus_smoothed / atr)
        denom = plus_di + minus_di
        dx[i] = 0.0 if denom == 0.0 else 100.0 * abs(plus_di - minus_di) / denom

    adx[first_adx_index] = sum(dx[first_dx_index : first_adx_index + 1]) / period
    for i in range(first_adx_index + 1, n):
        adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period

    return adx
