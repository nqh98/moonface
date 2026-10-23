from moonface.research.exogenous.backtest import (
    daily_returns, episode_trades, run_backtest)

def test_daily_returns_alignment():
    assert daily_returns([100.0, 110.0, 99.0]) == [0.1, -0.1]

def test_single_long_episode_r_is_vol_normalized():
    # positions decided each day; vol_window=2; constant prior vol
    # rets: [r0, r1, r2, r3]; long for the whole window
    rets = [0.0, 0.0, 0.05, 0.05]
    pos = [1, 1, 1, 1]
    # entry at i=2 (first index with vol_window history); episode over rets[2:]=+0.10
    trades = episode_trades(pos, rets, vol_window=2, cost=0.0)
    assert len(trades) == 1
    assert trades[0] > 0.0

def test_cost_charged_once_per_episode():
    rets = [0.0, 0.0, 0.01, 0.01]
    pos = [1, 1, 1, 1]
    gross = episode_trades(pos, rets, vol_window=2, cost=0.0)[0]
    net = episode_trades(pos, rets, vol_window=2, cost=0.002)[0]
    assert gross > net

def test_run_backtest_returns_summary():
    closes = [100.0 * (1.01 ** i) for i in range(60)]
    pos = [1] * 59
    s = run_backtest(closes, pos, vol_window=20, cost=0.001)
    assert s.trade_count >= 1
