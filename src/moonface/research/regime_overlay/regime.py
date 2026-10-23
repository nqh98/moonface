from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from moonface.research.exogenous.exo_features import aligned_value_at, pct_change

LAG_DAYS = 1
VIX_STRESS = 30.0
MOM_LOOKBACK_DAYS = 20
TREND_LOOKBACK_DAYS = 100


def _r1(ts_ms, macro):  # equity_riskon: SP500 20d momentum > 0
    ch = pct_change(macro.get("SP500", []), ts_ms, LAG_DAYS, MOM_LOOKBACK_DAYS)
    return None if ch is None else ch > 0.0


def _r2(ts_ms, macro):  # equity_trend: SP500 100d change > 0 (level above 100d-ago)
    ch = pct_change(macro.get("SP500", []), ts_ms, LAG_DAYS, TREND_LOOKBACK_DAYS)
    return None if ch is None else ch > 0.0


def _r3(ts_ms, macro):  # riskon_calm: momentum up AND VIX < stress
    ch = pct_change(macro.get("SP500", []), ts_ms, LAG_DAYS, MOM_LOOKBACK_DAYS)
    vix = aligned_value_at(macro.get("VIXCLS", []), ts_ms, LAG_DAYS)
    if ch is None or vix is None:
        return None
    return ch > 0.0 and vix < VIX_STRESS


def _r4(ts_ms, macro):  # dollar_weak: USD 20d change < 0
    ch = pct_change(macro.get("DTWEXBGS", []), ts_ms, LAG_DAYS, MOM_LOOKBACK_DAYS)
    return None if ch is None else ch < 0.0


@dataclass(frozen=True)
class RegimeDef:
    id: str
    name: str
    predicate: Callable[[int, dict], bool | None]


REGIME_DEFS: tuple[RegimeDef, ...] = (
    RegimeDef("R1", "equity_riskon", _r1),
    RegimeDef("R2", "equity_trend", _r2),
    RegimeDef("R3", "riskon_calm", _r3),
    RegimeDef("R4", "dollar_weak", _r4),
)


def regime_at(ts_ms: int, regime_def: RegimeDef, macro: dict) -> str:
    val = regime_def.predicate(ts_ms, macro)
    return "risk_on" if val is True else "risk_off"
