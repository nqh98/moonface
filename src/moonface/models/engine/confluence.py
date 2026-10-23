# src/moonface/signal/engine/confluence.py
from __future__ import annotations

from dataclasses import dataclass

from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import ModuleScore
from moonface.models.engine.modules.revert_book import (
    W_DIVERGENCE,
    W_FUND_CT,
    W_OI_FLUSH,
    W_RECLAIM,
    W_STRETCH,
    W_SWEEP,
)
from moonface.models.engine.modules.trend_book import (
    W_BREAKOUT,
    W_MA_ALIGN,
    W_MACRO,
    W_PULLBACK,
    W_ROC_STRONG,
)

# --- v2: macro gating matrix + two-book (TREND / MEAN_REVERT) aggregator ----

BASE_THRESHOLD = 60
TIER_A = 75
CT_SURCHARGE = 10
BREADTH_MIN = 3

# TREND book module -> max points (sum = 100). m5_funding has no named weight
# constant in trend_book; 15 is a documented literal (see trend_book.score).
_TREND_MAX: dict[str, int] = {
    "m1_macro": W_MACRO,
    "m2_breakout": W_BREAKOUT,
    "m2_ma_align": W_MA_ALIGN,
    "m3_roc": W_ROC_STRONG,
    "m4_pullback": W_PULLBACK,
    "m5_funding": 15,
}

# MEAN_REVERT book module -> max points (sum = 100).
_REVERT_MAX: dict[str, int] = {
    "m1_sweep": W_SWEEP,
    "m2_reclaim": W_RECLAIM,
    "m3_divergence": W_DIVERGENCE,
    "m4_fund_ct": W_FUND_CT,
    "m5_oi_flush": W_OI_FLUSH,
    "m6_stretch": W_STRETCH,
}

_DIRECTION_LABEL = {1: "LONG", -1: "SHORT"}
_ARCHETYPE_LABEL = {"trend": "TREND", "mean_revert": "MEAN_REVERT"}

# 1W Macro Gating Matrix (veto-only). Keys: (macro_effective, ARCHETYPE, DIRECTION).
GATE: dict[tuple[str, str, str], str] = {
    ("BEAR", "TREND", "LONG"): "REJECT",
    ("BEAR", "MEAN_REVERT", "LONG"): "ALLOW_CT",
    ("BEAR", "TREND", "SHORT"): "ALLOW",
    ("BEAR", "MEAN_REVERT", "SHORT"): "ALLOW",
    ("BULL", "TREND", "SHORT"): "REJECT",
    ("BULL", "MEAN_REVERT", "SHORT"): "ALLOW_CT",
    ("BULL", "TREND", "LONG"): "ALLOW",
    ("BULL", "MEAN_REVERT", "LONG"): "ALLOW",
}
for _archetype_label in ("TREND", "MEAN_REVERT"):
    for _direction_label in ("LONG", "SHORT"):
        GATE[("NEUTRAL", _archetype_label, _direction_label)] = "ALLOW"
del _archetype_label, _direction_label

# --- v2.2 policy layer (frozen constants; spec 2026-07-05) -------------------
# m4_pullback stays journaled in Decision.modules, but does not count toward the
# TREND book's score, breadth, or ceiling.
EXCLUDED_MODULES: tuple[str, ...] = ("m4_pullback",)
VETO_M4_EXCLUDED: str = "v2.2 m4_pullback excluded"

# --- v2.1 policy layer (frozen constants; spec 2026-07-04) -------------------
# Would-be-valid candidates blocked by policy journal as shadows so the
# horizon ablation can test each removal on forward data. TIER_A and
# CT_SURCHARGE above stay defined: CT_SURCHARGE still sets the ALLOW_CT
# validity threshold that defines a CT shadow, and diagnostics import both.
VETO_NO_CT = "v2.1 no counter-trend entries"
VETO_LONG_ONLY = "v2.1 long-only"


@dataclass(frozen=True)
class Decision:
    action: str
    direction: int
    archetype: str | None
    policy: str | None
    score: int
    max_attainable: int
    breadth: int
    tier: str | None
    veto: str | None
    shadow_score: int | None
    modules: tuple[ModuleScore, ...]
    detail: str
    shadow_direction: int | None = None


def _book_context(archetype: str, book: list[ModuleScore],
                  max_map: dict[str, int], macro_effective: str) -> dict:
    signed = sum(m.direction * m.points for m in book)
    direction = 1 if signed > 0 else (-1 if signed < 0 else 0)
    score = abs(signed)
    breadth = sum(1 for m in book if m.direction == direction and m.points > 0)
    max_attainable = sum(max_map.get(m.module, 0) for m in book if m.data_ok)

    policy: str | None = None
    threshold = BASE_THRESHOLD
    veto: str | None = None
    shadow_score: int | None = None
    shadow_direction: int | None = None
    valid = False
    tier: str | None = None

    if direction != 0:
        label = _ARCHETYPE_LABEL[archetype]
        direction_label = _DIRECTION_LABEL[direction]
        policy = GATE[(macro_effective, label, direction_label)]
        if policy == "REJECT":
            if breadth >= BREADTH_MIN and score >= BASE_THRESHOLD:
                veto = f"macro {macro_effective} vetoes {label} {direction_label.lower()}"
                shadow_score = score
                shadow_direction = direction
        else:
            if policy == "ALLOW_CT":
                threshold = BASE_THRESHOLD + CT_SURCHARGE
            valid = breadth >= BREADTH_MIN and score >= threshold
            if valid:
                tier = "B"

    return {
        "archetype": archetype, "direction": direction, "policy": policy,
        "score": score, "breadth": breadth, "max_attainable": max_attainable,
        "threshold": threshold, "tier": tier, "valid": valid,
        "veto": veto, "shadow_score": shadow_score,
        "shadow_direction": shadow_direction,
    }


def decide(trend_scores: list[ModuleScore], revert_scores: list[ModuleScore],
           macro: MacroState, cfg) -> Decision:
    del cfg  # decide is a pure function over the pre-scored books + macro state
    all_modules = tuple(trend_scores) + tuple(revert_scores)

    if macro.vol_state == "extreme":
        return Decision(
            action="WAIT", direction=0, archetype=None, policy=None,
            score=0, max_attainable=0, breadth=0, tier=None, veto=None,
            shadow_score=None, modules=all_modules,
            detail="extreme volatility — standing flat",
        )

    macro_effective = macro.effective()
    trend_scores_counted = [m for m in trend_scores
                            if m.module not in EXCLUDED_MODULES]
    trend_ctx = _book_context("trend", trend_scores_counted, _TREND_MAX,
                              macro_effective)
    revert_ctx = _book_context("mean_revert", revert_scores, _REVERT_MAX, macro_effective)

    # v2.1: counter-trend entries and trend shorts never trade. A candidate
    # that would have been valid under v2 rules becomes a journaled shadow.
    if revert_ctx["valid"]:
        revert_ctx["valid"] = False
        revert_ctx["veto"] = VETO_NO_CT
        revert_ctx["shadow_score"] = revert_ctx["score"]
        revert_ctx["shadow_direction"] = revert_ctx["direction"]
    if trend_ctx["valid"] and trend_ctx["direction"] < 0:
        trend_ctx["valid"] = False
        trend_ctx["veto"] = VETO_LONG_ONLY
        trend_ctx["shadow_score"] = trend_ctx["score"]
        trend_ctx["shadow_direction"] = trend_ctx["direction"]
    if not trend_ctx["valid"] and trend_ctx["veto"] is None:
        trend_full = _book_context("trend", trend_scores, _TREND_MAX,
                                   macro_effective)
        if trend_full["valid"] and trend_full["direction"] > 0:
            trend_ctx["veto"] = VETO_M4_EXCLUDED
            trend_ctx["shadow_score"] = trend_full["score"]
            trend_ctx["shadow_direction"] = trend_full["direction"]

    veto = trend_ctx["veto"] or revert_ctx["veto"]
    shadow_score = trend_ctx["shadow_score"] if trend_ctx["veto"] else revert_ctx["shadow_score"]
    shadow_direction = (trend_ctx["shadow_direction"]
                        if trend_ctx["veto"] else revert_ctx["shadow_direction"])

    candidates = [c for c in (trend_ctx, revert_ctx) if c["valid"]]

    if not candidates:
        lead = trend_ctx if trend_ctx["score"] >= revert_ctx["score"] else revert_ctx
        if veto:
            detail = (f"WAIT {veto}; shadow_score={shadow_score} score={lead['score']} "
                      f"thr={lead['threshold']} breadth={lead['breadth']}")
        else:
            detail = (f"WAIT score={lead['score']} thr={lead['threshold']} "
                      f"breadth={lead['breadth']} (below threshold)")
        return Decision(
            action="WAIT", direction=0, archetype=None, policy=None,
            score=lead["score"], max_attainable=lead["max_attainable"],
            breadth=lead["breadth"], tier=None, veto=veto,
            shadow_score=shadow_score, shadow_direction=shadow_direction,
            modules=all_modules, detail=detail,
        )

    if len(candidates) == 1:
        c = candidates[0]
        detail = (f"SETUP {c['archetype']} {_DIRECTION_LABEL[c['direction']]} "
                  f"score={c['score']} thr={c['threshold']} breadth={c['breadth']} "
                  f"tier={c['tier']}")
        return Decision(
            action="SETUP", direction=c["direction"], archetype=c["archetype"],
            policy=c["policy"], score=c["score"], max_attainable=c["max_attainable"],
            breadth=c["breadth"], tier=c["tier"], veto=veto,
            shadow_score=shadow_score, shadow_direction=shadow_direction,
            modules=all_modules, detail=detail,
        )

    if trend_ctx["direction"] != revert_ctx["direction"]:
        lead = trend_ctx if trend_ctx["score"] >= revert_ctx["score"] else revert_ctx
        detail = (f"WAIT books conflict score={lead['score']} thr={lead['threshold']} "
                  f"breadth={lead['breadth']}")
        return Decision(
            action="WAIT", direction=0, archetype=None, policy=None,
            score=lead["score"], max_attainable=lead["max_attainable"],
            breadth=lead["breadth"], tier=None, veto=veto,
            shadow_score=shadow_score, shadow_direction=shadow_direction,
            modules=all_modules, detail=detail,
        )

    winner = trend_ctx if trend_ctx["score"] >= revert_ctx["score"] else revert_ctx
    detail = (f"SETUP {winner['archetype']} {_DIRECTION_LABEL[winner['direction']]} "
              f"score={winner['score']} thr={winner['threshold']} breadth={winner['breadth']} "
              f"tier={winner['tier']}")
    return Decision(
        action="SETUP", direction=winner["direction"], archetype=winner["archetype"],
        policy=winner["policy"], score=winner["score"], max_attainable=winner["max_attainable"],
        breadth=winner["breadth"], tier=winner["tier"], veto=veto,
        shadow_score=shadow_score, shadow_direction=shadow_direction,
        modules=all_modules, detail=detail,
    )
