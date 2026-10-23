from moonface.core.stats import series_fingerprint, spearman
from moonface.core.models import Candle


def test_spearman_perfect_positive_correlation():
    assert spearman([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]) == 1.0


def test_spearman_needs_at_least_three_points():
    assert spearman([1.0, 2.0], [1.0, 2.0]) is None


def test_series_fingerprint_is_deterministic_and_content_sensitive():
    a = [Candle(0, 1.0, 1.0, 1.0, 1.0, 0.0), Candle(3_600_000, 2.0, 2.0, 2.0, 2.0, 0.0)]
    b = [Candle(0, 1.0, 1.0, 1.0, 1.0, 0.0), Candle(3_600_000, 2.0, 2.0, 2.0, 2.01, 0.0)]
    assert series_fingerprint(a) == series_fingerprint(a)
    assert series_fingerprint(a) != series_fingerprint(b)
