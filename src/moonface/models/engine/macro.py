from __future__ import annotations

from dataclasses import dataclass

from moonface.core.indicators import sma
from moonface.core.models import Candle

MACRO_MA_WEEKS = 30
MACRO_CONFIRM_CLOSES = 2


@dataclass(frozen=True)
class MacroState:
    bias: str
    confirmed: bool
    vol_state: str

    def effective(self) -> str:
        return self.bias if self.confirmed else "NEUTRAL"


def _side(close: float, ma: float) -> str:
    if close > ma:
        return "BULL"
    if close < ma:
        return "BEAR"
    return "NEUTRAL"


def classify_macro(weekly: list[Candle], vol_state: str, cfg) -> MacroState:
    del cfg  # macro bias is frozen off the weekly closes only
    closes = [c.close for c in weekly]
    if len(closes) < MACRO_MA_WEEKS + 1:
        return MacroState("NEUTRAL", False, vol_state)

    bias = "NEUTRAL"
    run_len = 0
    prev_side = "NEUTRAL"
    for i in range(MACRO_MA_WEEKS - 1, len(closes)):
        ma = sma(closes[i - MACRO_MA_WEEKS + 1:i + 1], MACRO_MA_WEEKS)
        side = _side(closes[i], ma)
        if side == "NEUTRAL":
            bias = "NEUTRAL"
            run_len = 0
            prev_side = side
            continue
        if side == prev_side:
            run_len += 1
        else:
            run_len = 1
            prev_side = side
        bias = side

    return MacroState(bias, run_len >= MACRO_CONFIRM_CLOSES, vol_state)
