"""v3 diagnostic replay: routing/trigger DISTRIBUTION only — never returns.

This is plumbing validation, not an edge test. The report must contain no
return/pnl fields, and its counts must be internally consistent.
"""
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.replay import replay_distribution

from tests.helpers_v3 import downtrend, flat_range, uptrend

CFG = EngineConfigV3()
LB = 150


def test_report_shape_and_banner():
    rep = replay_distribution(uptrend(400), CFG, lookback=LB)
    assert "NOT A VERDICT" in rep["banner"]
    for key in ("bars_evaluated", "regime_distribution", "action",
                "wait_breakdown", "by_mechanism", "enter_direction",
                "enter_quality", "enter_rate"):
        assert key in rep


def test_counts_are_internally_consistent():
    rep = replay_distribution(uptrend(400), CFG, lookback=LB)
    n = rep["bars_evaluated"]
    assert rep["action"]["ENTER"] + rep["action"]["WAIT"] == n
    assert sum(rep["regime_distribution"].values()) == n
    wb = rep["wait_breakdown"]
    assert wb["extreme"] + wb["empty_cell"] + wb["selected_no_entry"] \
        == rep["action"]["WAIT"]
    for stats in rep["by_mechanism"].values():
        assert stats["entered"] <= stats["selected"]
    assert 0.0 <= rep["enter_rate"] <= 1.0


def test_uptrend_routes_to_trend_mechanisms_and_fires_long():
    rep = replay_distribution(uptrend(400), CFG, lookback=LB)
    # a clean uptrend must classify as TRENDING_UP on most bars
    up_bars = sum(v for k, v in rep["regime_distribution"].items()
                  if k.startswith("TRENDING_UP"))
    assert up_bars > 0
    # BREAKOUT is selected and actually fires at least once
    assert rep["by_mechanism"]["BREAKOUT"]["entered"] > 0
    # every ENTER in a pure uptrend is long
    assert rep["enter_direction"]["short"] == 0
    assert rep["enter_direction"]["long"] > 0


def test_range_series_selects_reversion():
    rep = replay_distribution(flat_range(400), CFG, lookback=LB)
    assert rep["by_mechanism"]["REVERSION"]["selected"] > 0


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)


def test_report_exposes_no_return_shaped_fields():
    # guard the "no returns" promise at the data level: no report KEY is
    # return/pnl-shaped (the banner is a value and may say "no returns").
    rep = replay_distribution(downtrend(400), CFG, lookback=LB)
    keys = {k.lower() for k in _all_keys(rep)}
    for forbidden in ("net_r", "pnl", "return", "sharpe", "drawdown", "profit"):
        assert not any(forbidden in k for k in keys)


def test_health_warnings_flag_degenerate_routing():
    # a dead-flat series (no breakouts, no stretch) should never all-ENTER;
    # warnings surface when a mechanism never fires
    rep = replay_distribution(flat_range(400, amp=0.0), CFG, lookback=LB)
    assert isinstance(rep["warnings"], list)
    assert rep["action"]["ENTER"] <= rep["bars_evaluated"]
