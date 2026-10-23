import pytest

from moonface.core.models import Candle
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.ensemble import (cell_weight, _to_market,
                                                ensemble_distribution, _trailing_rank,
                                                assign_regimes, replay_ensemble,
                                                run_ensemble_to_doc)
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Distribution
from moonface.research.pathsig.walkforward import Fold

_RVOL = FEATURE_NAMES.index("rvol_24")
_MA = FEATURE_NAMES.index("ma100_dist")


def _sample(index, rvol=0.0, ma=0.0):
    x = [0.0] * len(FEATURE_NAMES)
    x[_RVOL] = rvol
    x[_MA] = ma
    x[FEATURE_NAMES.index("atr_frac")] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(0.0, 0.0, 0.0))


def test_trailing_rank_is_point_in_time():
    vals = [1.0, 2.0, 3.0, 0.5]
    assert _trailing_rank(vals, 0, 180) == 0.0          # no prior -> 0.0
    assert _trailing_rank(vals, 2, 180) == 1.0          # 3.0 beats 1.0, 2.0
    assert _trailing_rank(vals, 3, 180) == 0.0          # 0.5 below all priors


def test_assign_regimes_buckets_and_point_in_time():
    # rising rvol and |ma| so late bars rank high on both axes -> regime 3
    samples = [_sample(i, rvol=float(i), ma=float(i)) for i in range(50)]
    regimes = assign_regimes(samples, window=180)
    assert set(regimes) <= {0, 1, 2, 3}
    assert regimes[0] == 0                               # no prior -> low/range
    assert regimes[-1] == 3                              # high vol + trend
    # a late spike must not change an earlier bar's regime
    before = list(regimes)
    samples2 = samples + [_sample(999, rvol=1e9, ma=1e9)]
    assert assign_regimes(samples2, window=180)[:50] == before


def test_cell_weight_clamps_non_positive_and_none():
    assert cell_weight(None) == 0.0
    assert cell_weight(Distribution(0.5, 0.0, 0.0, 0.0)) == 0.0      # mae 0
    assert cell_weight(Distribution(0.5, -1.0, -2.0, 1.0)) == 0.0    # edge < 0
    w = cell_weight(Distribution(0.6, 1.0, -2.0, 3.0))
    assert w == 0.5                                                   # 1.0 / 2.0


def test_to_market_short_flips_frame():
    d = Distribution(p_up=0.7, exp_ret_r=1.0, exp_mae_r=-0.5, exp_mfe_r=2.0)
    assert _to_market(d, "LONG") == d
    m = _to_market(d, "SHORT")
    assert m.p_up == pytest.approx(0.3) and m.exp_ret_r == -1.0
    assert m.exp_mae_r == -2.0 and m.exp_mfe_r == 0.5


def test_ensemble_distribution_weight_average_and_netting():
    long_d = Distribution(0.7, 1.0, -1.0, 2.0)
    short_d = Distribution(0.7, 1.0, -1.0, 2.0)     # same in its own frame
    # opposing equal-weight signals net toward zero drift
    ens = ensemble_distribution([(_to_market(long_d, "LONG"), 1.0),
                                 (_to_market(short_d, "SHORT"), 1.0)])
    assert ens.exp_ret_r == pytest.approx(0.0)
    assert ens.p_up == pytest.approx(0.5)
    assert ensemble_distribution([]) is None
    assert ensemble_distribution([(long_d, 0.0)]) is None


def _wall_sample(index):
    x = [0.0] * len(FEATURE_NAMES)
    x[FEATURE_NAMES.index("atr_frac")] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(ret_r=0.4, mae_r=-1.0, mfe_r=0.8))


def test_replay_ensemble_reports_both_frames():
    samples = [_wall_sample(i) for i in range(60)]
    regimes = [0] * 60                              # single regime
    fires = {0: {i: "LONG" for i in range(60)}}     # one signal, always LONG
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_ensemble(samples, folds, regimes, fires, edge_threshold=0.05,
                          kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                          slippage_bps=2.0, min_events=10, trial_srs=[0.1, 0.2],
                          drawdown_cap_r=15.0)
    assert res["status"] == "ok"
    assert "risk_adjusted" in res and "fixed_cap" in res
    assert res["n_trades"] >= 1
    assert isinstance(res["fixed_cap"]["within_cap"], bool)


def test_replay_ensemble_waits_when_no_cells_fit():
    samples = [_wall_sample(i) for i in range(60)]
    regimes = [0] * 60
    fires = {0: {0: "LONG"}}                         # only one fired bar -> below min_events
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_ensemble(samples, folds, regimes, fires, edge_threshold=0.05,
                          kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                          slippage_bps=2.0, min_events=10, trial_srs=[],
                          drawdown_cap_r=15.0)
    assert res["status"] == "no_trades"


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


def test_run_ensemble_to_doc_schema_and_verdict():
    rung0 = {"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}
    doc = run_ensemble_to_doc(_readers(500), n_folds=2, horizons=[6],
                              pool_symbols=["ETHUSDT"], rung0_doc=rung0)
    assert doc["config"]["horizons"] == [6]
    r1 = doc["rung1"][0]
    assert r1["h"] == 6 and r1["status"] in {"ok", "no_trades"}
    v = doc["verdict"][0]
    assert isinstance(v["beats_rung0"], bool)
    assert isinstance(v["clears_gate"], bool)
