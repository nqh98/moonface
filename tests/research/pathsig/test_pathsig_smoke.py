# tests/test_pathsig_smoke.py
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.pathsig.dataset import build_dataset
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.policy import Distribution, decide
from moonface.research.pathsig.walkforward import walk_forward_folds

_ATR_FRAC_I = FEATURE_NAMES.index("atr_frac")  # cost denominator; look up, don't hardcode index 4

H4 = 14_400_000


def _bundle(n):
    candles, funding, feat = [], [], []
    for i in range(n):
        price = 100.0 + 10.0 * (i % 50)  # cyclical, tradeable excursions
        candles.append(Candle(timestamp_ms=i * H4, open=price,
                              high=price * 1.02, low=price * 0.98,
                              close=price, volume=1.0))
        funding.append(0.0001)
        feat.append(1000.0 + i)
    return DataBundle(candles=candles, funding=funding, feature=feat)


def _daily(n):
    return [Candle(timestamp_ms=i * 86_400_000, open=100.0 + i, high=101.0 + i,
                  low=99.0 + i, close=100.0 + i, volume=1.0) for i in range(n)]


def test_pipeline_runs_end_to_end():
    bundle = _bundle(600)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 600, xs_funding_rank=[0.5] * 600,
                            d1_candles=_daily(120), w1_candles=_daily(40))
    assert len(samples) > 50
    folds = walk_forward_folds(len(samples), n_folds=3, embargo=6,
                               lockbox_fraction=0.2)
    assert folds

    # constant "predictor": always mildly bullish -> exercises LONG + WAIT paths
    def predict(_x):
        return Distribution(p_up=0.55, exp_ret_r=0.3, exp_mae_r=-1.0,
                            exp_mfe_r=1.0)

    fold = folds[-1]
    # the chosen fold must not reach into the sealed 20% lockbox tail
    assert max(fold.test_idx) < int(len(samples) * (1 - 0.2))
    decisions, labels, atr_fracs, fundings = [], [], [], []
    for pos in fold.test_idx:
        s = samples[pos]
        dist = predict(s.x)
        decisions.append(decide(dist, edge_threshold=0.2, kelly_scale=0.02,
                                max_fraction=0.02))
        labels.append(s.label)
        atr_fracs.append(s.x[_ATR_FRAC_I])
        fundings.append(0.0)

    assert len(decisions) == len(fold.test_idx)
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=5.0, slippage_bps=2.0, n_trials=10,
                            trial_srs=[], drawdown_cap_r=15.0)
    assert res["risk_adjusted"]["trade_count"] >= 1
    assert 0.0 <= res["risk_adjusted"]["dsr"] <= 1.0
    assert isinstance(res["fixed_cap"]["within_cap"], bool)
