"""Structural 'regime-flip' exit for the MTF lane.

The frozen exits are chart/price rules -- a fixed time hold, a static ATR stop.
This exit is different in kind: it is the HTF regime read itself, inverted. Hold
the trade until the same point-in-time HTF bias that authorized the entry stops
supporting it -- the trend flips sign, or (for the regime-QUALITY gate) decays
back into chop so the bias returns to 0 -- capped at max_bars as a backstop.

Because it needs the aligned HTF bias, it lives in the mtf package rather than
the shared, frozen foundation exit registry. Its R uses the identical 1*ATR
denominator and COST_FRACTION model as single_trade_r, so every number it
produces is directly comparable to horizon_hold / horizon_wide_stop / atr_trail.
No look-ahead: bias[j] is read from HTF bars already closed by base bar j's close
(combine.htf_bias_series), and the fill is that same bar's close.
"""
from __future__ import annotations

from moonface.core.metrics import COST_FRACTION
from moonface.core.risk import risk_unit
from moonface.research.mtf.combine import htf_bias_series
from moonface.research.mtf.grid import BASE_TF, BIAS_FNS, MtfCell


def bias_for(candles, cell: MtfCell) -> list[int]:
    """The point-in-time HTF bias series aligned to base bars -- the same read
    the entry gate uses, reused here as the exit signal."""
    return htf_bias_series(candles, BASE_TF, cell.htf, BIAS_FNS[cell.bias_fn],
                           cell.bias_params)


def regime_flip_r(candles, i: int, side: str, params: dict,
                  bias: list[int]) -> tuple[float, float] | None:
    """(net R, atr_frac) for one entry exited at the first bar after i where the
    regime bias no longer supports the trade side, else at the max_bars backstop.
    Mirrors single_trade_r's R math (gross move / 1*ATR at entry, minus cost)."""
    unit = risk_unit(candles, i, 1.0, params["atr_period"])
    if unit is None:
        return None
    want = 1 if side == "LONG" else -1
    sign = 1.0 if side == "LONG" else -1.0
    entry = candles[i].close
    end = min(i + params["max_bars"], len(candles) - 1)
    exit_idx = end
    for j in range(i + 1, end + 1):
        if bias[j] != want:              # trend flipped or decayed into chop
            exit_idx = j
            break
    gross = sign * (candles[exit_idx].close - entry) / unit
    atr_frac = unit / entry
    return round(gross - COST_FRACTION / atr_frac, 4), atr_frac
