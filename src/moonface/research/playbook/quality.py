from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.playbook.config import PlaybookParams, OVEREXTENDED, SUPPORTIVE
from moonface.research.playbook.regime import efficiency_ratio
from moonface.research.playbook.setups import Setup


@dataclass(frozen=True)
class QualityResult:
    passed: bool
    reasons: list[str]


def quality_check(h1_prefix: list[Candle], setup: Setup, regime: str,
                  params: PlaybookParams) -> QualityResult:
    reasons: list[str] = []
    closes = [c.close for c in h1_prefix]
    a = atr(h1_prefix, params.atr_period)
    risk = abs(setup.entry - setup.invalidation)

    if regime == OVEREXTENDED:
        reasons.append("post_exhaustion")
    if regime not in SUPPORTIVE:
        reasons.append("regime_mismatch")
    if efficiency_ratio(closes, params.slope_n) < params.chop_eff_floor:
        reasons.append("too_choppy")
    if a > 0 and (setup.entry - setup.ref_level) > params.max_entry_atr * a:
        reasons.append("late_extended")
    if a > 0 and risk > params.max_risk_atr * a:
        reasons.append("entry_far_from_invalidation")
    if a > 0 and risk > 0:
        reward = 2.0 * a            # structural target proxy = 2*ATR
        if reward / risk < params.min_rr:
            reasons.append("poor_rr")
    if risk <= 0:
        reasons.append("poor_rr")
    if setup.name == "vol_compression_expansion" and a > 0:
        if (h1_prefix[-1].high - h1_prefix[-1].low) < params.min_expansion_atr * a:
            reasons.append("weak_expansion")
    return QualityResult(passed=not reasons, reasons=reasons)
