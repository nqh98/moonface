"""C1 tier repair: pool-adjacent-violators over the frozen score buckets."""
from moonface.models.engine.repair import (
    apply_tier_merge,
    c1_entry_threshold,
    fit_tier_merge,
)

from tests.helpers_repair import ht


def _bucket_trades(spec):
    """spec: list of (score, mean_net_r, n)."""
    out = []
    i = 0
    for score, mean, n in spec:
        for _ in range(n):
            out.append(ht(i, score, mean))
            i += 10
    return out


def test_identity_when_bucket_means_monotone():
    train = _bucket_trades(
        [(20, -0.2, 10), (50, -0.1, 10), (65, 0.1, 10), (80, 0.3, 10)])
    assert fit_tier_merge(train) == (40, 60, 75)


def test_inverted_top_bucket_merges_into_tier_b():
    train = _bucket_trades(
        [(20, -0.2, 10), (50, -0.1, 10), (65, 0.3, 10), (80, 0.0, 10)])
    assert fit_tier_merge(train) == (40, 60)


def test_empty_bucket_merges_left():
    # [40,60) has no trades: it is absorbed leftward before PAVA
    train = _bucket_trades([(20, -0.2, 10), (65, 0.1, 10), (80, 0.3, 10)])
    assert fit_tier_merge(train) == (60, 75)


def test_underpowered_input_returns_identity():
    assert fit_tier_merge([]) == (40, 60, 75)
    assert fit_tier_merge(_bucket_trades([(65, 0.1, 5)])) == (40, 60, 75)


def test_apply_and_entry_threshold():
    edges = (40, 60)
    assert apply_tier_merge(30, edges) == 0
    assert apply_tier_merge(45, edges) == 1
    assert apply_tier_merge(60, edges) == 2
    assert apply_tier_merge(90, edges) == 2
    assert c1_entry_threshold((40, 60)) == 60
    assert c1_entry_threshold((40, 60, 75)) == 60
    assert c1_entry_threshold((40,)) == 40
    assert c1_entry_threshold(()) == 0
