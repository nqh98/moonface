# tests/test_engine_confluence.py
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.confluence import (VETO_LONG_ONLY, VETO_M4_EXCLUDED,
                                               VETO_NO_CT, decide)
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import ModuleScore


def _cfg(**kw):
    return EngineConfig(**kw)


# --- decide() : macro gating matrix + two-book aggregator (v2) ---------------

def _m(module, direction, points, archetype="trend", data_ok=True):
    return ModuleScore(module=module, direction=direction, points=points,
                       archetype=archetype, data_ok=data_ok, evidence=())


def _macro(bias, confirmed=True, vol_state="normal"):
    return MacroState(bias, confirmed, vol_state)


# Note: the plan's illustrative scores (68 / 72 / 58) are not multiples of 5,
# which conflicts with ModuleScore.__post_init__'s points % 5 == 0 invariant
# (any sum of multiple-of-5 points is itself a multiple of 5). The tests below
# substitute the nearest multiple-of-5 values that preserve the exact same
# boundary semantics relative to BASE_THRESHOLD/TIER_A/CT_SURCHARGE
# (65 < 70, 70 <= 75 < 85, 85 >= 85).


def test_bear_vetoes_trend_long():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]
    d = decide(trend, [], _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto
    assert d.shadow_score == 60
    assert d.shadow_direction == 1


def test_m4_exclusion_shadow_journals_when_full_book_would_fire():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 10),
        _m("m4_pullback", 1, 15),
    ]  # counted 50 -> WAIT; with m4: 65, breadth 4, NEUTRAL ALLOW -> v2.1 valid
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.score == 50
    assert d.veto == VETO_M4_EXCLUDED
    assert d.shadow_score == 65
    assert d.shadow_direction == 1


def test_no_m4_shadow_when_counted_book_fires():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # counted 60 -> SETUP; the exclusion changed nothing gate-relevant
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.score == 60
    assert d.veto is None


def test_m4_shadow_not_journaled_for_full_short():
    trend = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 20),
        _m("m4_pullback", -1, 15),
    ]  # counted short 60 -> long-only veto; full book stays blocked and no m4 shadow
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.veto == VETO_LONG_ONLY
    assert d.shadow_score == 60
    assert d.shadow_direction == -1


def test_bear_vetoes_mean_revert_short():
    revert = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 20),
        _m("m4_pullback", -1, 20),
    ]
    d = decide(revert, [], _macro("BULL"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto
    assert d.shadow_score == 60
    assert d.shadow_direction == -1


def test_bear_mean_revert_long_below_ct_threshold_waits():
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 15, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
    ]  # score = 65, breadth 4, ALLOW_CT threshold 70
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"


def test_would_be_ct_setup_is_vetoed_with_shadow():
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
    ]  # score 75, breadth 4, ALLOW_CT threshold 70 -> valid under v2 rules
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 75
    assert d.shadow_direction == 1


def test_m4_shadow_yields_to_macro_veto():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # counted 60 >= 60, breadth 3 — BEAR REJECT macro-veto fires first
    d = decide(trend, [], _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto is not None and d.veto.startswith("macro")
    assert d.shadow_score == 60
    assert d.shadow_direction == 1


def test_high_score_ct_candidate_also_vetoed():
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
        _m("m5_oi_flush", 1, 10, "mean_revert"),
    ]  # score 85 — would have been Tier A in v2
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 85


def test_ct_short_candidate_vetoed_with_shadow():
    revert = [
        _m("m1_sweep", -1, 20, "mean_revert"),
        _m("m2_reclaim", -1, 15, "mean_revert"),
        _m("m4_fund_ct", -1, 15, "mean_revert"),
        _m("m5_oi_flush", -1, 10, "mean_revert"),
    ]  # score 60, breadth 4, ALLOW threshold 60 -> valid under v2 rules
    d = decide([], revert, _macro("BEAR"), _cfg())
    assert d.action == "WAIT"
    assert d.veto == VETO_NO_CT
    assert d.shadow_direction == -1


def test_unconfirmed_bear_does_not_gate():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]
    macro = _macro("BEAR", confirmed=False)
    assert macro.effective() == "NEUTRAL"
    d = decide(trend, [], macro, _cfg())
    assert d.action == "SETUP"
    assert d.veto is None
    assert d.shadow_score is None
    assert d.shadow_direction is None


def test_breadth_guard_rejects_thin_book():
    trend = [
        _m("m1_macro", 1, 40),
        _m("m2_breakout", 1, 35),
    ]  # score 75 from only 2 non-zero modules
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.breadth == 2


def test_ct_conflict_no_longer_blocks_trend_long():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]  # trend LONG score 60 after excluding m4_pullback
    revert = [
        _m("m1_sweep", -1, 20, "mean_revert"),
        _m("m2_reclaim", -1, 15, "mean_revert"),
        _m("m3_divergence", -1, 25, "mean_revert"),
        _m("m4_fund_ct", -1, 15, "mean_revert"),
        _m("m5_oi_flush", -1, 5, "mean_revert"),
    ]  # revert SHORT score 80 -> v2.1 shadow, not a conflicting candidate
    d = decide(trend, revert, _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.direction == 1
    assert d.archetype == "trend"
    assert d.score == 60
    assert d.veto == VETO_NO_CT
    assert d.shadow_direction == -1


def test_trend_wins_when_revert_candidate_is_vetoed():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 10),
    ]  # trend LONG score 60 after excluding m4_pullback
    revert = [
        _m("m1_sweep", 1, 20, "mean_revert"),
        _m("m2_reclaim", 1, 15, "mean_revert"),
        _m("m3_divergence", 1, 25, "mean_revert"),
        _m("m4_fund_ct", 1, 15, "mean_revert"),
        _m("m5_oi_flush", 1, 5, "mean_revert"),
    ]  # revert LONG score 80 -> shadow; trend candidate trades
    d = decide(trend, revert, _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.direction == 1
    assert d.archetype == "trend"
    assert d.score == 60
    assert d.veto == VETO_NO_CT
    assert d.shadow_score == 80


def test_trend_short_vetoed_long_only():
    trend = [
        _m("m1_macro", -1, 20),
        _m("m2_breakout", -1, 20),
        _m("m3_roc", -1, 20),
        _m("m4_pullback", -1, 20),
    ]  # trend SHORT score 60, NEUTRAL macro -> valid under v2, shadowed now
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0
    assert d.veto == VETO_LONG_ONLY
    assert d.shadow_score == 60
    assert d.shadow_direction == -1


def test_trend_long_high_score_tier_stays_b():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 10),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
    ]  # score 85 — would have been Tier A in v2; v2.1 has one tier
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.tier == "B"


def test_degraded_ceiling_drops_max_attainable():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 10),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
        _m("m5_funding", 0, 0, data_ok=False),
    ]
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.max_attainable == 70


def test_degraded_ceiling_still_uses_absolute_threshold():
    # score 55 with m5_funding degraded (ceiling drops to 70) — still WAITs,
    # threshold stays the absolute 60, not rescaled to the reduced ceiling.
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 15),
        _m("m3_roc", 0, 0),
        _m("m4_pullback", 0, 0),
        _m("m5_funding", 0, 0, data_ok=False),
    ]
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.max_attainable == 70


def test_extreme_vol_forces_flat_v2():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 20),
    ]
    macro = _macro("NEUTRAL", vol_state="extreme")
    d = decide(trend, [], macro, _cfg())
    assert d.action == "WAIT"
    assert d.direction == 0


def test_every_wait_detail_reports_score_threshold_breadth():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
    ]  # score 40, breadth 2 -> WAIT
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.detail
    assert str(d.score) in d.detail
    assert "thr=" in d.detail
    assert str(d.breadth) in d.detail


def test_m4_pullback_points_do_not_count_toward_score_or_breadth():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 15),
        _m("m3_roc", 1, 10),
        _m("m4_pullback", 1, 10),
    ]  # counted 45 / breadth 3; even with m4 it is 55 < 60, so the
    #    exclusion shadow cannot fire either
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "WAIT"
    assert d.score == 45
    assert d.breadth == 3
    assert d.veto is None
    # the module is still scored and journaled via Decision.modules
    assert any(m.module == "m4_pullback" and m.points == 10
               for m in d.modules)


def test_max_attainable_excludes_m4():
    trend = [
        _m("m1_macro", 1, 20),
        _m("m2_breakout", 1, 20),
        _m("m2_ma_align", 1, 10),
        _m("m3_roc", 1, 20),
        _m("m4_pullback", 1, 15),
        _m("m5_funding", 1, 15),
    ]
    d = decide(trend, [], _macro("NEUTRAL"), _cfg())
    assert d.action == "SETUP"
    assert d.score == 85           # 100 signed minus m4's 15
    assert d.max_attainable == 85  # m4's 15 is no longer attainable
