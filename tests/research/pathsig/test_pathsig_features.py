# tests/test_pathsig_features.py
from moonface.core.models import Candle
from moonface.research.pathsig.features import (FEATURE_NAMES,
                                                build_feature_rows, to_vector)

H4 = 14_400_000


def _candles(closes):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(timestamp_ms=i * H4, open=c, high=c * 1.01,
                          low=c * 0.99, close=c, volume=1.0))
    return out


def test_feature_names_are_frozen_and_unique():
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))
    assert "ret_1" in FEATURE_NAMES
    assert "rvol_24" in FEATURE_NAMES


def test_rows_are_none_until_warmup_satisfied():
    candles = _candles([100.0 + i for i in range(200)])
    rows = build_feature_rows(candles, atr_period=14)
    assert len(rows) == len(candles)
    # earliest bars cannot have the longest-lookback feature
    assert rows[0] is None
    # a late bar has a full base row: exactly the 7 base-block keys
    assert rows[150] is not None
    BASE_KEYS = {"ret_1", "ret_6", "ret_24", "rvol_24", "atr_frac",
                 "ma100_dist", "donchian_pos_55"}
    assert set(rows[150].keys()) == BASE_KEYS
    # the base block is a subset of the frozen full vector
    assert BASE_KEYS.issubset(set(FEATURE_NAMES))


def test_to_vector_is_order_stable():
    # to_vector projects a COMPLETE row (all FEATURE_NAMES present) in frozen
    # order. build_feature_rows returns only the base block; build_dataset
    # (Task 5) produces the complete rows that to_vector consumes.
    row = {name: float(k) for k, name in enumerate(FEATURE_NAMES)}
    vec = to_vector(row)
    assert len(vec) == len(FEATURE_NAMES)
    # to_vector follows FEATURE_NAMES order exactly
    assert vec[FEATURE_NAMES.index("ret_1")] == row["ret_1"]
    assert vec == [row[name] for name in FEATURE_NAMES]


def test_zscore_handles_nullable_series():
    from moonface.research.pathsig.features import zscore
    series = [1.0, 2.0, None, 4.0, 5.0]
    # None current value -> None (no crash)
    assert zscore(series, i=2, n=3) is None
    # window with <2 non-None values -> None
    assert zscore([1.0, None, None], i=2, n=3) is None
    # normal case computes a real z-score
    v = zscore([1.0, 2.0, 3.0, 4.0, 5.0], i=4, n=5)
    assert v is not None and v > 0
