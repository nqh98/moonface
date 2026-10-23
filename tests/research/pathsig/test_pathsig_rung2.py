# tests/test_pathsig_rung2.py
# ruff: noqa: E402  (numpy + rung2 imports must follow pytest.importorskip)
import pytest

# numpy backs only the optional rung-2 distributional-forest path; skip when the
# extra isn't installed (`pip install -e ".[pathsig]"`).
pytest.importorskip("numpy")
import numpy as np

from moonface.core.models import Candle
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision
from moonface.research.pathsig.forest import PathPrediction
from moonface.research.pathsig.policy import Distribution
from moonface.research.pathsig.rung2 import (X_matrix, labels_matrix,
                                             ruin_clamp, RUIN_Q05_R,
                                             fit_config, replay_positions,
                                             inner_split, select_config,
                                             STRUCTURE_GRID, EDGE_THRESHOLDS,
                                             replay_forest, rung2_verdict,
                                             _rung0_floor, _rung1_result,
                                             open_lockbox, run_rung2_to_doc)
from moonface.research.pathsig.walkforward import walk_forward_folds

_ATR = FEATURE_NAMES.index("atr_frac")


def _sample(index, feat0=0.0, ret=0.0):
    x = [0.0] * len(FEATURE_NAMES)
    x[0] = feat0
    x[_ATR] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(ret_r=ret, mae_r=-1.0, mfe_r=1.0))


def test_matrix_builders_shapes_and_order():
    samples = [_sample(i, feat0=float(i), ret=float(i) / 10.0) for i in range(5)]
    pos = [0, 2, 4]
    X = X_matrix(samples, pos)
    L = labels_matrix(samples, pos)
    assert X.shape == (3, len(FEATURE_NAMES))
    assert L.shape == (3, 3)
    assert X[1, 0] == 2.0                      # second selected sample's feat0
    assert L[2, 0] == pytest.approx(0.4)       # ret of sample index 4


def test_ruin_clamp_zeroes_dangerous_long():
    pred = PathPrediction(dist=Distribution(0.6, 1.0, -1.0, 2.0),
                          q05=RUIN_Q05_R - 1.0, q50=0.0, q95=2.0)
    clamped = ruin_clamp(Decision("LONG", 0.01), pred)
    assert clamped == Decision("WAIT", 0.0)


def test_ruin_clamp_passes_safe_trade():
    pred = PathPrediction(dist=Distribution(0.6, 1.0, -1.0, 2.0),
                          q05=RUIN_Q05_R + 1.0, q50=0.0, q95=2.0)
    dec = Decision("LONG", 0.01)
    assert ruin_clamp(dec, pred) == dec


def test_ruin_clamp_uses_negative_q95_for_short():
    # for a SHORT, the adverse tail is the upper return tail (-q95)
    pred = PathPrediction(dist=Distribution(0.4, -1.0, -1.0, 2.0),
                          q05=0.0, q50=0.0, q95=-RUIN_Q05_R + 1.0)
    assert ruin_clamp(Decision("SHORT", 0.01), pred) == Decision("WAIT", 0.0)


def _learnable(n=400):
    # feat0 sign predicts ret sign; mae/mfe symmetric, atr fixed
    samples = []
    rng = np.random.default_rng(0)
    for i in range(n):
        f0 = float(rng.normal())
        ret = 1.0 if f0 > 0 else -1.0
        x = [0.0] * len(FEATURE_NAMES)
        x[0] = f0
        x[_ATR] = 0.02
        samples.append(Sample(index=i, timestamp_ms=i, x=x,
                              label=PathLabel(ret_r=ret, mae_r=-0.5, mfe_r=1.5)))
    return samples


def test_fit_config_predicts_learnable_sign():
    samples = _learnable(400)
    forest = fit_config(samples, list(range(400)), structure=(5, 30, 4))
    x = np.array(samples[0].x)
    x[0] = 3.0
    assert forest.predict(x).dist.exp_ret_r > 0


def test_replay_positions_trades_learnable_and_scores():
    samples = _learnable(400)
    forest = fit_config(samples, list(range(300)), structure=(5, 30, 4))
    res = replay_positions(samples, list(range(300, 400)), forest,
                           edge_threshold=0.10, n_trials=1, trial_srs=[])
    assert res["status"] == "ok"
    assert res["n_trades"] > 0
    assert res["fixed_cap"]["total_r"] > 0      # positive on a learnable signal


def test_replay_positions_no_trades_when_threshold_too_high():
    samples = _learnable(200)
    forest = fit_config(samples, list(range(150)), structure=(3, 60, 4))
    res = replay_positions(samples, list(range(150, 200)), forest,
                           edge_threshold=100.0, n_trials=1, trial_srs=[])
    assert res["status"] == "no_trades"


def test_inner_split_purges_and_is_disjoint():
    train = list(range(100))
    inner_train, inner_test = inner_split(train, embargo=6)
    assert set(inner_train).isdisjoint(inner_test)
    assert max(inner_train) + 6 <= min(inner_test)      # embargo gap respected
    assert inner_test[-1] == 99                          # inner test is the tail


def test_select_config_returns_grid_member_and_trial_srs():
    samples = _learnable(400)
    choice = select_config(samples, list(range(400)), embargo=6)
    assert choice.structure in STRUCTURE_GRID
    assert choice.edge_threshold in EDGE_THRESHOLDS
    # every (structure, threshold) that produced trades contributes a trial SR
    assert len(choice.trial_srs) >= 1
    assert len(choice.trial_srs) <= len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS)


def test_replay_forest_runs_nested_and_scores_learnable():
    samples = _learnable(600)
    folds = walk_forward_folds(len(samples), n_folds=2, embargo=6,
                               lockbox_fraction=0.2)
    res = replay_forest(samples, folds, h=6, n_trials=48)
    assert res["status"] == "ok"
    assert res["n_trades"] > 0
    assert "selected" in res and len(res["selected"]) == len(folds)


def test_replay_forest_no_folds_is_no_trades():
    samples = _learnable(50)
    res = replay_forest(samples, [], h=6, n_trials=48)
    assert res["status"] == "no_trades"


def _ok_result(total_r, dsr):
    return {"status": "ok", "h": 6,
            "fixed_cap": {"total_r": total_r, "max_drawdown_r": -5.0,
                          "within_cap": True},
            "risk_adjusted": {"sharpe": 0.2, "dsr": dsr, "mar": 0.3}}


def test_rung0_floor_and_rung1_lookup_by_horizon():
    rung0 = {"rows": [
        {"family": "a", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 9.3}, "risk_adjusted": {"dsr": 0.0}},
        {"family": "b", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 4.0}, "risk_adjusted": {"dsr": 0.0}}]}
    assert _rung0_floor(rung0, 6)["best_total_r"] == 9.3
    rung1 = {"rung1": [{"status": "ok", "h": 6,
                        "fixed_cap": {"total_r": -22.0},
                        "risk_adjusted": {"dsr": 0.0}}]}
    assert _rung1_result(rung1, 6)["fixed_cap"]["total_r"] == -22.0


def test_verdict_requires_beating_both_and_gate():
    result = _ok_result(total_r=30.0, dsr=0.96)
    v = rung2_verdict(result, floor={"best_total_r": 9.3},
                      rung1={"fixed_cap": {"total_r": -22.0},
                             "risk_adjusted": {"dsr": 0.0}})
    assert v["beats_rung0"] and v["beats_rung1"] and v["clears_gate"]

    weak = _ok_result(total_r=5.0, dsr=0.50)
    v2 = rung2_verdict(weak, floor={"best_total_r": 9.3},
                       rung1={"fixed_cap": {"total_r": -22.0},
                              "risk_adjusted": {"dsr": 0.0}})
    assert v2["beats_rung0"] is False and v2["clears_gate"] is False


H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_run_rung2_to_doc_schema_and_verdict():
    rung0 = {"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}
    rung1 = {"rung1": [{"status": "ok", "h": 6,
                        "fixed_cap": {"total_r": -22.0, "max_drawdown_r": -64.0,
                                      "within_cap": False},
                        "risk_adjusted": {"sharpe": 0.0, "dsr": 0.0, "mar": -0.1}}]}
    doc = run_rung2_to_doc(_readers(500), n_folds=2, horizons=[6],
                           pool_symbols=["ETHUSDT"], rung0_doc=rung0,
                           rung1_doc=rung1)
    assert doc["config"]["horizons"] == [6]
    assert doc["config"]["n_trials"] == len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS)
    r2 = doc["rung2"][0]
    assert r2["h"] == 6 and r2["status"] in {"ok", "no_trades"}
    v = doc["verdict"][0]
    assert isinstance(v["beats_rung0"], bool)
    assert isinstance(v["beats_rung1"], bool)
    assert isinstance(v["clears_gate"], bool)


def test_open_lockbox_scores_only_the_tail():
    samples = _learnable(600)
    res = open_lockbox(samples, h=6, n_trials=48)
    assert res["status"] in {"ok", "no_trades"}
    # tail size = total minus usable (1 - lockbox_fraction)
    usable = int(len(samples) * (1.0 - 0.2))
    assert res["n_events"] == len(samples) - usable
