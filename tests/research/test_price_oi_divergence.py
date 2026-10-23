from moonface.research.price_oi_divergence import (
    N_TRIALS, control_for, divergence_specs, stage2_of,
    stage4_of)


def test_grid_is_four_short_only_cells():
    specs = divergence_specs()
    assert len(specs) == N_TRIALS == 4
    ks = {s.entry["params"]["k"] for s in specs}
    ls = {s.entry["params"]["lookback"] for s in specs}
    ws = {s.entry["params"]["window"] for s in specs}
    assert ks == {1.5, 2.0}
    assert ls == {3, 6}
    assert ws == {180}
    for s in specs:
        assert s.entry["family"] == "price_oi_divergence"
        assert s.asset["timeframe"] == "1h"
        assert s.asset["metrics_field"] == "sum_open_interest"


def test_control_swaps_family_keeps_everything_else():
    spec = divergence_specs()[0]
    ctrl = control_for(spec)
    assert ctrl.entry["family"] == "price_extension_short"
    assert ctrl.entry["params"] == spec.entry["params"]
    assert ctrl.asset == spec.asset
    assert ctrl.exit == spec.exit
    assert ctrl.fraction == spec.fraction


def test_stage_gates_require_dominance_and_floors():
    dom = {"holdout_treatment_mar": 1.2, "holdout_treatment_dd": -0.2,
           "holdout_dominance": True}
    assert stage2_of(dom) is True
    assert stage2_of({**dom, "holdout_dominance": False}) is False
    assert stage2_of({**dom, "holdout_treatment_dd": -0.5}) is False

    tail = {"tail_treatment_mar": 1.1, "tail_treatment_dd": -0.1,
            "tail_trades": 25, "tail_dominance": True}
    assert stage4_of(tail) is True
    assert stage4_of({**tail, "tail_trades": 19}) is False
