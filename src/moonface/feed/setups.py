"""SMC setup detection for the feed. A Setup is emitted when a confirming event
(sweep->CHOCH reversal, or BOS continuation) lands exactly on a given candle.
Frozen to the falsified advisor's detector constants so behavior is reproducible."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.core.smc import (classify_structure, detect_bos, detect_choch,
                                     detect_liquidity, detect_sweeps)

# Frozen detector constants (mirror research/edge/smc_variants.py).
WARMUP = 60
N_PERIODS = 5
ATR_PERIOD = 14
DISPLACEMENT_MULT = 1.5
WINDOW_CAP = 100
LOOKBACK = 30


@dataclass(frozen=True)
class Setup:
    setup_type: str                       # "sweep_choch" | "bos_continuation"
    side: str                             # "LONG" | "SHORT"
    confirm_index: int
    entry_close: float
    swept_level: float | None
    struct_level: float | None
    atr_value: float


def _window(candles: list[Candle], i: int) -> list[Candle]:
    return candles[max(0, i + 1 - WINDOW_CAP): i + 1]


def _sweep_choch_at(candles: list[Candle], i: int) -> Setup | None:
    """A sell-side sweep followed by a bullish CHOCH (mirror for short), with the
    CHOCH confirming exactly at index i."""
    if i < WARMUP:
        return None
    window = _window(candles, i)
    a = atr(window, ATR_PERIOD)
    if a <= 0:
        return None
    tol = max(0.25 * a, 1e-9)
    pools = detect_liquidity(window, tolerance=tol).pools
    sweeps = detect_sweeps(window, pools)
    min_index = max(0, len(window) - LOOKBACK)
    recent = [s for s in sweeps if s.index >= min_index]
    if not recent:
        return None
    sweep = recent[-1]
    rev_direction = "BULLISH" if sweep.side == "SELL" else "BEARISH"
    event = detect_choch(window, rev_direction, sweep.index, a,
                         DISPLACEMENT_MULT, N_PERIODS)
    if event is None or event.index != i:
        return None
    side = "LONG" if rev_direction == "BULLISH" else "SHORT"
    return Setup("sweep_choch", side, i, candles[i].close,
                 sweep.pool_level, event.level, a)


def _bos_at(candles: list[Candle], i: int) -> Setup | None:
    """Trend-continuation BOS confirming exactly at index i: in a BULLISH
    structure, a wide close above the last swing high (LONG); BEARISH mirror."""
    if i < WARMUP:
        return None
    window = _window(candles, i)
    a = atr(window, ATR_PERIOD)
    if a <= 0:
        return None
    struct = classify_structure(window, N_PERIODS)
    if struct.trend == "NEUTRAL":
        return None
    event = detect_bos(window, struct.trend, i - 1, a,
                       DISPLACEMENT_MULT, N_PERIODS)
    if event is None or event.index != i:
        return None
    side = "LONG" if struct.trend == "BULLISH" else "SHORT"
    return Setup("bos_continuation", side, i, candles[i].close,
                 None, event.level, a)


_FINDERS = (_sweep_choch_at, _bos_at)


def detect_all(candles: list[Candle]) -> list[Setup]:
    out: list[Setup] = []
    for i in range(WARMUP, len(candles)):
        for finder in _FINDERS:
            s = finder(candles, i)
            if s is not None:
                out.append(s)
    return out


def detect_last(candles: list[Candle]) -> list[Setup]:
    if not candles:
        return []
    last = len(candles) - 1
    return [s for finder in _FINDERS
            for s in [finder(candles, last)] if s is not None]
