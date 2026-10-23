"""Decomposition variants of the falsified SMC advisor entry.

Each generator has signature (candles, params) -> list[(index, "LONG"|"SHORT")],
matching edge.signals. They reuse the frozen _smc.py detectors and the same
warmup/window-cap/ATR/displacement constants as smc_continuation, so the
decomposition is faithful to the advisor tested in PROGRAM_CONCLUSION cycles 1-2.

Research-only: NOT registered in edge.signals.REGISTRY; never feeds the drift
screen or any promotion path. The WAIT stance is unchanged by this module.
"""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.edge._smc import (classify_structure, detect_choch,
                                         detect_liquidity, detect_sweeps)

Entry = tuple[int, str]

# Frozen to the falsified advisor's values (mirror of edge.signals).
_WARMUP = 60
_N_PERIODS = 5
_ATR_PERIOD = 14
_DISPLACEMENT_MULT = 1.5
_WINDOW_CAP = 100


def _window(h1: list[Candle], i: int) -> list[Candle]:
    return h1[max(0, i + 1 - _WINDOW_CAP): i + 1]


def _reversal_events(h1: list[Candle], lookback: int) -> list[tuple[int, str]]:
    """The falsified advisor's sweep -> CHOCH -> reversal trigger.

    For each bar i >= _WARMUP: on the last _WINDOW_CAP bars, detect liquidity
    pools/sweeps; take the most recent sweep within `lookback` bars; invert it
    into a structural direction (SELL-side sweep -> bullish reversal); confirm
    with a CHOCH+displacement. Returns (i, reversal_side) where reversal_side is
    the advisor's traded direction. Identical in trigger to
    edge.signals.smc_continuation, which returns the *flipped* side."""
    out: list[tuple[int, str]] = []
    for i in range(_WARMUP, len(h1) - 1):
        window = _window(h1, i)
        a = atr(window, _ATR_PERIOD)
        if a <= 0:
            continue
        tol = max(0.25 * a, 1e-9)
        pools = detect_liquidity(window, tolerance=tol).pools
        sweeps = detect_sweeps(window, pools)
        min_index = max(0, len(window) - lookback)
        recent = [s for s in sweeps if s.index >= min_index]
        if not recent:
            continue
        sweep = recent[-1]
        rev_direction = "BULLISH" if sweep.side == "SELL" else "BEARISH"
        event = detect_choch(window, rev_direction, sweep.index, a,
                             _DISPLACEMENT_MULT, _N_PERIODS)
        if event is None:
            continue
        reversal_side = "LONG" if rev_direction == "BULLISH" else "SHORT"
        out.append((i, reversal_side))
    return out


def full_reversal(h1: list[Candle], params: dict) -> list[Entry]:
    """The falsified advisor: sweep -> CHOCH -> reversal. LONG after a SELL-side
    sweep confirmed by a bullish CHOCH (mirror for SHORT)."""
    return _reversal_events(h1, params["lookback"])


def flip(h1: list[Candle], params: dict) -> list[Entry]:
    """Inverted side at every reversal trigger == edge.signals.smc_continuation."""
    return [(i, "SHORT" if side == "LONG" else "LONG")
            for i, side in _reversal_events(h1, params["lookback"])]


def sweep_only(h1: list[Candle], params: dict) -> list[Entry]:
    """Enter in the swept direction on the most recent sweep within `lookback`
    (SELL-side sweep -> LONG). No structural confirmation: isolates the raw
    liquidity-grab concept."""
    lookback = params["lookback"]
    out: list[Entry] = []
    for i in range(_WARMUP, len(h1) - 1):
        window = _window(h1, i)
        a = atr(window, _ATR_PERIOD)
        if a <= 0:
            continue
        tol = max(0.25 * a, 1e-9)
        pools = detect_liquidity(window, tolerance=tol).pools
        sweeps = detect_sweeps(window, pools)
        min_index = max(0, len(window) - lookback)
        recent = [s for s in sweeps if s.index >= min_index]
        if not recent:
            continue
        sweep = recent[-1]
        out.append((i, "LONG" if sweep.side == "SELL" else "SHORT"))
    return out


def choch_only(h1: list[Candle], params: dict) -> list[Entry]:
    """Enter on a CHOCH that completes on the last bar: a wide displacement
    close beyond the most recent opposing swing. Isolates change-of-character
    with no sweep precondition. The lookback window cap bounds cost to O(cap)."""
    out: list[Entry] = []
    for i in range(_WARMUP, len(h1) - 1):
        window = _window(h1, i)
        a = atr(window, _ATR_PERIOD)
        if a <= 0:
            continue
        last = len(window) - 1
        bull = detect_choch(window, "BULLISH", last - 1, a,
                            _DISPLACEMENT_MULT, _N_PERIODS)
        bear = detect_choch(window, "BEARISH", last - 1, a,
                            _DISPLACEMENT_MULT, _N_PERIODS)
        if bull is not None and bull.index == last:
            out.append((i, "LONG"))
        elif bear is not None and bear.index == last:
            out.append((i, "SHORT"))
    return out


def structure_bias(h1: list[Candle], params: dict) -> list[Entry]:
    """Trend-follow the swing structure map (BULLISH -> LONG, BEARISH -> SHORT),
    emitting only on regime transitions. Isolates the HTF bias concept."""
    n_periods = params.get("n_periods", _N_PERIODS)
    out: list[Entry] = []
    prev = "NEUTRAL"
    for i in range(_WARMUP, len(h1) - 1):
        trend = classify_structure(_window(h1, i), n_periods).trend
        if trend == "BULLISH" and prev != "BULLISH":
            out.append((i, "LONG"))
        elif trend == "BEARISH" and prev != "BEARISH":
            out.append((i, "SHORT"))
        prev = trend
    return out
