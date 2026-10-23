from moonface.research.exogenous.exo_features import aligned_value_at, DAY_MS
from moonface.research.exogenous.fred_data import MacroPoint

# series sampled at day 0,1,2 (UTC midnights) with values 10, 20, 30
PTS = [MacroPoint(0, 10.0), MacroPoint(DAY_MS, 20.0), MacroPoint(2 * DAY_MS, 30.0)]


def test_uses_only_published_values_with_lag():
    # lag = 1 day: value sampled at day 1 publishes at day 2.
    # decision at day 2 (exactly) sees day-1 value (20), NOT day-2 value (30).
    assert aligned_value_at(PTS, 2 * DAY_MS, publish_lag_days=1) == 20.0


def test_no_lookahead_before_first_publication():
    # decision at day 0 with lag 1: nothing is published yet -> None
    assert aligned_value_at(PTS, 0, publish_lag_days=1) is None


def test_forward_fill_across_gap():
    # decision midway between publications holds the last published value
    assert aligned_value_at(PTS, 2 * DAY_MS + DAY_MS // 2, publish_lag_days=0) == 30.0


def test_shifting_future_value_does_not_change_past_decision():
    # GATING: mutating the (unpublished-at-decision) day-2 point must not change
    # a decision taken at day 1 (lag 0).
    base = aligned_value_at(PTS, DAY_MS, publish_lag_days=0)
    mutated = aligned_value_at(
        [MacroPoint(0, 10.0), MacroPoint(DAY_MS, 20.0), MacroPoint(2 * DAY_MS, 999.0)],
        DAY_MS, publish_lag_days=0)
    assert base == mutated == 20.0
