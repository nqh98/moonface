"""SMC structure/liquidity detectors used by the (falsified) smc_continuation
and reversion_in_range probe families. Inlined here so the probe leaderboards
stay reproducible after the SMC advisor's removal. Private to edge/."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from moonface.core.models import Candle, Side, Trend


@dataclass(frozen=True)
class LiquidityPool:
    side: Side
    level: float
    indexes: tuple[int, int]
    swept: bool


@dataclass(frozen=True)
class LiquidityContext:
    pools: list[LiquidityPool]


@dataclass(frozen=True)
class Sweep:
    side: Side  # "SELL" = sell-side liquidity swept (bullish intent); "BUY" = buy-side swept
    pool_level: float
    index: int


def detect_liquidity(candles: list[Candle], tolerance: float = 0.5) -> LiquidityContext:
    pools: list[LiquidityPool] = []
    for i in range(len(candles) - 1):
        for j in range(i + 1, len(candles)):
            if abs(candles[i].high - candles[j].high) <= tolerance:
                level = (candles[i].high + candles[j].high) / 2
                swept = any(c.high > level for k, c in enumerate(candles) if k > j)
                pools.append(LiquidityPool("BUY", round(level, 2), (i, j), swept))
            if abs(candles[i].low - candles[j].low) <= tolerance:
                level = (candles[i].low + candles[j].low) / 2
                swept = any(c.low < level for k, c in enumerate(candles) if k > j)
                pools.append(LiquidityPool("SELL", round(level, 2), (i, j), swept))
    return LiquidityContext(pools=pools)


def detect_sweeps(candles: list[Candle], pools: list[LiquidityPool]) -> list[Sweep]:
    """A sweep is a candle that wicks beyond a pool level and closes back inside.
    Sell-side sweep (low wicks below a SELL pool, closes above) -> bullish intent.
    Buy-side sweep (high wicks above a BUY pool, closes below) -> bearish intent."""
    sweeps: list[Sweep] = []
    for pool in pools:
        formed_at = pool.indexes[1]
        for index in range(formed_at + 1, len(candles)):
            current = candles[index]
            if pool.side == "SELL" and current.low < pool.level <= current.close:
                sweeps.append(Sweep("SELL", pool.level, index))
            if pool.side == "BUY" and current.high > pool.level >= current.close:
                sweeps.append(Sweep("BUY", pool.level, index))
    return sweeps


@dataclass(frozen=True)
class Swings:
    highs: list[tuple[int, float]]
    lows: list[tuple[int, float]]


@dataclass(frozen=True)
class StructureEvent:
    kind: Literal["BOS", "CHOCH"]
    direction: Trend
    index: int
    level: float


@dataclass(frozen=True)
class StructureState:
    trend: Trend
    swings: Swings
    swing_high: float | None
    swing_low: float | None


def find_swings(candles: list[Candle], n_periods: int = 5) -> Swings:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(n_periods, len(candles) - n_periods):
        left = candles[index - n_periods : index]
        right = candles[index + 1 : index + n_periods + 1]
        current = candles[index]
        if all(current.high > candle.high for candle in left + right):
            highs.append((index, current.high))
        if all(current.low < candle.low for candle in left + right):
            lows.append((index, current.low))
    return Swings(highs=highs, lows=lows)


def classify_structure(candles: list[Candle], n_periods: int = 5) -> StructureState:
    swings = find_swings(candles, n_periods)
    swing_high = swings.highs[-1][1] if swings.highs else None
    swing_low = swings.lows[-1][1] if swings.lows else None
    trend: Trend = "NEUTRAL"
    if len(swings.highs) >= 2 and len(swings.lows) >= 2:
        higher_high = swings.highs[-1][1] > swings.highs[-2][1]
        higher_low = swings.lows[-1][1] > swings.lows[-2][1]
        lower_high = swings.highs[-1][1] < swings.highs[-2][1]
        lower_low = swings.lows[-1][1] < swings.lows[-2][1]
        if higher_high and higher_low:
            trend = "BULLISH"
        elif lower_high and lower_low:
            trend = "BEARISH"
    return StructureState(
        trend=trend,
        swings=swings,
        swing_high=swing_high,
        swing_low=swing_low,
    )


def detect_choch(
    candles: list[Candle],
    direction: Trend,
    start_index: int,
    atr_value: float,
    displacement_mult: float,
    n_periods: int = 5,
) -> StructureEvent | None:
    """First displacement candle after start_index that breaks the most recent
    opposing structural swing in `direction`. CHOCH = change of character."""
    if atr_value <= 0:
        return None
    swings = find_swings(candles, n_periods)
    if direction == "BULLISH":
        levels = [level for idx, level in swings.highs if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close > broken_level and wide:
                return StructureEvent("CHOCH", "BULLISH", index, broken_level)
        return None
    if direction == "BEARISH":
        levels = [level for idx, level in swings.lows if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close < broken_level and wide:
                return StructureEvent("CHOCH", "BEARISH", index, broken_level)
        return None
    return None


def detect_bos(
    candles: list[Candle],
    direction: Trend,
    start_index: int,
    atr_value: float,
    displacement_mult: float = 1.5,
    n_periods: int = 5,
) -> StructureEvent | None:
    """Trend-continuation Break of Structure: the first displacement candle after
    ``start_index`` that closes beyond the most recent SAME-direction structural
    swing. BULLISH -> close above the last swing high (continuation LONG);
    BEARISH -> close below the last swing low (continuation SHORT). Mirrors
    ``detect_choch`` but breaks the same-side swing instead of the opposing one."""
    if atr_value <= 0:
        return None
    swings = find_swings(candles, n_periods)
    if direction == "BULLISH":
        levels = [level for idx, level in swings.highs if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close > broken_level and wide:
                return StructureEvent("BOS", "BULLISH", index, broken_level)
        return None
    if direction == "BEARISH":
        levels = [level for idx, level in swings.lows if idx <= start_index]
        if not levels:
            return None
        broken_level = levels[-1]
        for index in range(start_index + 1, len(candles)):
            current = candles[index]
            wide = (current.high - current.low) >= displacement_mult * atr_value
            if current.close < broken_level and wide:
                return StructureEvent("BOS", "BEARISH", index, broken_level)
        return None
    return None

__all__ = [
    "LiquidityPool", "LiquidityContext", "Sweep", "Swings",
    "StructureEvent", "StructureState",
    "detect_liquidity", "detect_sweeps", "find_swings",
    "classify_structure", "detect_choch", "detect_bos",
]
