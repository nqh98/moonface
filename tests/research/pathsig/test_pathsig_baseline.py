from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.pathsig.baseline import (
    _mirror,
    fit_distribution,
    replay_fired,
    replay_signal,
    run_baseline_to_doc,
)
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.walkforward import Fold


def _sample(index, label):
    return Sample(index=index, timestamp_ms=index, x=[0.0] * 16, label=label)


def test_mirror_short_flips_frame():
    lbl = PathLabel(ret_r=1.5, mae_r=-0.8, mfe_r=2.0)
    assert _mirror(lbl, "LONG") == lbl
    m = _mirror(lbl, "SHORT")
    assert m.ret_r == -1.5
    assert m.mae_r == -2.0   # was mfe (>=0) -> negated
    assert m.mfe_r == 0.8    # was mae (<=0) -> negated


def test_fit_distribution_is_train_mean():
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0)),
               _sample(1, PathLabel(-1.0, -2.0, 1.0)),
               _sample(2, PathLabel(0.0, 0.0, 0.0))]   # not fired
    fire = {0: "LONG", 1: "LONG"}
    dist = fit_distribution(samples, fire, [0, 1, 2], min_events=2)
    assert dist.exp_ret_r == 0.5            # mean of 2.0, -1.0
    assert dist.exp_mae_r == -1.5
    assert dist.exp_mfe_r == 2.0
    assert dist.p_up == 0.5                 # one of two has ret_r > 0


def test_fit_distribution_too_few_returns_none():
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0))]
    assert fit_distribution(samples, {0: "LONG"}, [0], min_events=2) is None


def test_fit_distribution_ignores_non_train_labels():
    # changing a label outside the train positions must not change the fit
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0)),
               _sample(1, PathLabel(99.0, -99.0, 99.0))]
    fire = {0: "LONG", 1: "LONG"}
    dist = fit_distribution(samples, fire, [0], min_events=1)
    assert dist.exp_ret_r == 2.0


def _wall_samples(n=60):
    # positive drift but large adverse excursion -> the structural wall
    out = []
    for i in range(n):
        x = [0.0] * 16
        x[FEATURE_NAMES.index("atr_frac")] = 0.02
        out.append(_sample(i, PathLabel(ret_r=0.3, mae_r=-2.0, mfe_r=0.5)))
        out[-1] = Sample(index=i, timestamp_ms=i, x=x, label=out[-1].label)
    return out


def test_replay_fired_reports_both_frames():
    samples = _wall_samples(60)
    fire = {i: "LONG" for i in range(60)}
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_fired(fire, samples, folds, h=6, edge_threshold=0.05,
                       kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                       slippage_bps=2.0, min_events=10, n_trials=16,
                       drawdown_cap_r=15.0)
    assert res["status"] == "ok"
    assert "risk_adjusted" in res and "fixed_cap" in res
    assert res["n_trades"] >= 0
    assert isinstance(res["fixed_cap"]["within_cap"], bool)


def test_replay_fired_too_few_events():
    samples = _wall_samples(60)
    fire = {0: "LONG"}   # only one fired bar, below min_events
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_fired(fire, samples, folds, h=6, edge_threshold=0.05,
                       kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                       slippage_bps=2.0, min_events=10, n_trials=16,
                       drawdown_cap_r=15.0)
    assert res["status"] == "too_few_events"


def test_replay_signal_reports_no_data_when_series_missing():
    samples = _wall_samples(60)
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    bundle = DataBundle(candles=[], funding=None)   # funding_fade needs funding
    res = replay_signal("funding_fade", {"window": 60, "z_thr": 1.5}, bundle,
                        samples, folds, h=6, edge_threshold=0.05,
                        kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                        slippage_bps=2.0, min_events=10, n_trials=16,
                        drawdown_cap_r=15.0)
    assert res["status"] == "no_data"


H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0, "SOLUSDT": 20.0}.get(sym)
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


def test_run_baseline_to_doc_schema_and_statuses():
    doc = run_baseline_to_doc(_readers(500), n_folds=2, horizons=[6],
                              pool_symbols=["ETHUSDT", "SOLUSDT"])
    assert doc["config"]["horizons"] == [6]
    assert doc["config"]["n_trials"] == len(doc["rows"])
    statuses = {r["status"] for r in doc["rows"]}
    assert statuses <= {"ok", "no_data", "too_few_events"}
    # bookdepth is None -> the two ob_imbalance_follow rows must be no_data
    ob = [r for r in doc["rows"] if r["family"] == "ob_imbalance_follow"]
    assert ob and all(r["status"] == "no_data" for r in ob)
