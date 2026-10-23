"""Gate-3 replay machinery: live-shape stream under a scoring qualifier."""
import dataclasses

from moonface.models.engine.calibration import scoring_pass
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.repair import (
    gate3_replay,
    qualifier_stream,
    qualify_fn_for,
    replay_metrics,
)

from tests.helpers_audit import _walk_series
from tests.helpers_repair import ht


def _fixture():
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    rows = scoring_pass(cfg, candles, 380)
    return candles, cfg, rows


def test_stream_is_long_only_non_overlapping_with_atr_frac():
    candles, cfg, rows = _fixture()
    pairs = qualifier_stream(candles, cfg, rows, lambda row: True)
    prev_exit = -1
    for trade, atr_frac in pairs:
        assert trade.direction == 1
        assert trade.entry_index > prev_exit
        assert atr_frac > 0.0
        prev_exit = trade.exit_index
    assert qualifier_stream(candles, cfg, rows, lambda row: False) == []


def test_replay_metrics_drawdown_and_cost_stress():
    cfg = EngineConfig()
    pairs = [(ht(0, 70, 1.0), 0.02), (ht(10, 70, -2.0), 0.02),
             (ht(20, 70, 0.5), 0.02)]
    m = replay_metrics(pairs, cfg)
    assert m["n"] == 3
    assert abs(m["net_r"] - (-0.5)) < 1e-9
    assert abs(m["max_dd_r"] - (-2.0)) < 1e-9
    assert m["cost_stress"]["net_r_3x"] < m["cost_stress"]["net_r_1x"]


def test_identity_candidate_replays_identically_to_baseline():
    candles, cfg, rows = _fixture()
    result = gate3_replay(candles, cfg, rows, "c1_tier_merge", (40, 60, 75))
    assert result["baseline_v22"] == result["candidate"]
    assert result["passed"] == (
        result["candidate"]["n"] > 0
        and result["candidate"]["cost_stress"]["net_r_3x"] > 0)


def test_qualify_fn_dispatch():
    assert callable(qualify_fn_for("c1_tier_merge", (40, 60)))
    assert callable(qualify_fn_for("c2_side_vol", {("LONG", "normal"): 5}))
    assert callable(qualify_fn_for("c3_isotonic", ((60, 0.1),)))
