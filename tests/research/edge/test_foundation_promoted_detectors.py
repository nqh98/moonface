from __future__ import annotations

from moonface.core.models import Candle
from moonface.core.smc import (
    LiquidityPool, LiquidityContext, Sweep, Swings, StructureEvent, StructureState,  # noqa: F401
    detect_liquidity, detect_sweeps, find_swings, classify_structure, detect_choch,  # noqa: F401
)
from moonface.core.pivots import PivotCtx, daily_pivots
# Shims must still expose the same names at the old paths.
from moonface.research.edge._smc import detect_liquidity as _shim_liq
from moonface.research.edge.pivots import daily_pivots as _shim_piv


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


def test_foundation_detect_liquidity_and_shim_match():
    candles = [_c(0, 100, 110, 95, 105), _c(1, 105, 110.2, 100, 106), _c(2, 106, 108, 101, 102)]
    assert any(p.side == "BUY" for p in detect_liquidity(candles, tolerance=0.5).pools)
    assert any(p.side == "BUY" for p in _shim_liq(candles, tolerance=0.5).pools)


def test_foundation_pivots_and_shim_match():
    # daily_pivots assigns each bar the PRIOR UTC day's pivot (lookahead-free);
    # the second candle sits on day 1 (ts=86_400_000) so it reads day 0's
    # HLC (120/90/105 from the first candle) and yields the expected PivotCtx.
    series = [Candle(0, 100, 120, 90, 105, 1.0), Candle(86_400_000, 130, 140, 125, 135, 1.0)]
    assert daily_pivots(series)[-1] == _shim_piv(series)[-1] == PivotCtx(
        p=105.0, r1=120.0, s1=90.0, r2=135.0, s2=75.0, r3=150.0, s3=60.0)
