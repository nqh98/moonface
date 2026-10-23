from moonface.research.exogenous.evaluate import dsr_of_trades, walk_forward_summaries
from moonface.research.exogenous.fred_data import MacroPoint
from moonface.research.exogenous.exo_features import DAY_MS
from moonface.research.exogenous.grid import StateDef


def test_dsr_zero_for_noise():
    noise = [0.1, -0.1, 0.05, -0.05, 0.02, -0.02] * 5
    assert 0.0 <= dsr_of_trades(noise, n_trials=6) <= 1.0


def test_walk_forward_splits_into_windows(monkeypatch):
    import moonface.research.exogenous.evaluate as ev

    closes = [100.0 * (1.005 ** i) for i in range(120)]
    ts = [i * DAY_MS for i in range(119)]
    series = {"X": [MacroPoint(0, 1.0)]}
    # force always-long via a single always-active +1 state
    state = (StateDef("a", "X", 0, 0, ">", 0.0, +1),)
    monkeypatch.setattr(ev, "PRECOMMITTED_STATES", state)
    wins, agg = walk_forward_summaries(closes, ts, series, n_windows=4)
    assert len(wins) == 4
    assert agg.trade_count >= 1
