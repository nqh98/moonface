import random

from moonface.core.bundle import DataBundle
from moonface.kernel.divergence_null import block_shuffle, surrogate_null
from moonface.research.price_oi_divergence import divergence_specs


def test_block_shuffle_preserves_length_and_multiset():
    feat = [float(i) for i in range(50)]
    out = block_shuffle(feat, block_len=7, rng=random.Random(1))
    assert len(out) == len(feat)
    assert sorted(out) == sorted(feat)


def test_block_shuffle_rejects_nonpositive_block():
    import pytest
    with pytest.raises(ValueError):
        block_shuffle([1.0, 2.0], 0, random.Random(0))


def test_surrogate_null_fails_when_no_real_edge():
    from dataclasses import dataclass

    @dataclass
    class Candle:
        timestamp_ms: int
        open: float
        high: float
        low: float
        close: float
        volume: float

    n = 400
    candles = [Candle(i * 3_600_000, 100.0, 100.0, 100.0, 100.0, 1.0)
               for i in range(n)]
    feature = [1000.0] * n
    research = DataBundle(candles=candles, feature=feature)
    spec = divergence_specs()[0]
    result = surrogate_null(spec, research, draws=20)
    assert result["real_mar"] == 0.0
    assert result["passed"] is False
    assert 0.0 < result["p_value"] <= 1.0


def test_surrogate_null_requires_feature():
    import pytest
    from dataclasses import dataclass

    @dataclass
    class Candle:
        timestamp_ms: int
        open: float
        high: float
        low: float
        close: float
        volume: float

    research = DataBundle(candles=[Candle(0, 1, 1, 1, 1, 1)], feature=None)
    with pytest.raises(ValueError):
        surrogate_null(divergence_specs()[0], research, draws=5)
