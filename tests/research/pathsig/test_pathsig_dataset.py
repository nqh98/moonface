# tests/test_pathsig_dataset.py
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.pathsig.dataset import Sample, build_dataset
from moonface.research.pathsig.features import FEATURE_NAMES

H4 = 14_400_000


def _bundle(n):
    candles, funding, feat = [], [], []
    for i in range(n):
        price = 100.0 + i * 0.5
        candles.append(Candle(timestamp_ms=i * H4, open=price, high=price * 1.01,
                              low=price * 0.99, close=price, volume=1.0))
        funding.append(0.0001)
        feat.append(1000.0 + i)   # stand-in OI/metrics series
    return DataBundle(candles=candles, funding=funding, feature=feat)


def _daily(n):
    return [Candle(timestamp_ms=i * 86_400_000, open=100.0 + i, high=101.0 + i,
                  low=99.0 + i, close=100.0 + i, volume=1.0) for i in range(n)]


def test_samples_have_complete_vectors_and_labels():
    bundle = _bundle(300)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 300, xs_funding_rank=[0.5] * 300,
                            d1_candles=_daily(60), w1_candles=_daily(20))
    assert samples, "expected non-empty dataset"
    s = samples[0]
    assert isinstance(s, Sample)
    assert len(s.x) == len(FEATURE_NAMES)
    assert all(v is not None for v in s.x)
    # indices are strictly increasing and within range
    idxs = [s.index for s in samples]
    assert idxs == sorted(idxs)


def test_last_horizon_bars_excluded_for_missing_label():
    bundle = _bundle(300)
    samples = build_dataset(bundle, h=6, atr_period=14,
                            xs_ret_rank=[0.5] * 300, xs_funding_rank=[0.5] * 300,
                            d1_candles=_daily(60), w1_candles=_daily(20))
    assert max(s.index for s in samples) < 300 - 6
