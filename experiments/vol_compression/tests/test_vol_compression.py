import numpy as np
import pandas as pd
import pytest

from vol_compression_backtest import (
    load_data, log_returns, realized_vol, rolling_pct_threshold,
    _apply_cooldown, VolCompressionStrategy, straddle_payoffs,
    block_bootstrap_ci, slice_stats, verdict, _SQRT_2_OVER_PI,
)


def _closes_from_rets(rets):
    """Price path (base 100) whose successive log-returns equal `rets`."""
    return 100.0 * np.exp(np.concatenate([[0.0], np.cumsum(rets)]))


def _df_from_closes(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="h", tz="UTC")
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1.0},
                        index=idx)


# ---- loader / features ----

def test_load_data_parses_utc(tmp_path):
    base = pd.Timestamp("2020-01-01", tz="UTC")
    rows = [[int((base + pd.Timedelta(hours=h)).timestamp() * 1000),
             100.0, 101.0, 99.0, 100.0, 5.0] for h in range(6)]
    p = tmp_path / "o.csv"
    pd.DataFrame(rows).to_csv(p, header=False, index=False)
    df = load_data(str(p))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and len(df) == 6


def test_log_returns_and_realized_vol():
    close = pd.Series([100, 110, 121, 133.1, 146.41],
                      index=pd.date_range("2020-01-01", periods=5, freq="h", tz="UTC"))
    r = log_returns(close)
    assert r.iloc[1] == pytest.approx(np.log(1.1))
    rv = realized_vol(close, 3)          # constant 10% returns -> std 0
    assert rv.iloc[3] == pytest.approx(0.0, abs=1e-12)


# ---- compression trigger ----

def test_compression_fires_calm_not_high_vol():
    rets = ([0.03, -0.03] * 15) + ([0.0001, -0.0001] * 5) + ([0.03, -0.03] * 10)
    df = _df_from_closes(_closes_from_rets(rets))
    sig = VolCompressionStrategy(rv_period=3, comp_window_days=1, cooldown_bars=1,
                                 comp_pct=20).compression_signals(df)
    # calm block is close-indices ~31..40; a high-vol bar well after (~55) should
    # NOT fire because the calm bars have entered its trailing threshold window.
    assert sig.iloc[33:41].any()
    assert not bool(sig.iloc[55])


def test_apply_cooldown_logic():
    raw = np.zeros(60, dtype=bool)
    raw[[10, 15, 40]] = True
    acc = _apply_cooldown(raw, 24)
    assert list(np.flatnonzero(acc)) == [10, 40]  # 15 suppressed (within 24 of 10)


def test_threshold_no_future_leak():
    rets = ([0.02, -0.02] * 20) + ([0.0002, -0.0002] * 10)
    df = _df_from_closes(_closes_from_rets(rets))
    strat = VolCompressionStrategy(rv_period=3, comp_window_days=1)
    thr1 = rolling_pct_threshold(strat.feature_vol(df), strat.comp_window, strat.comp_pct)
    df2 = df.copy()
    df2.iloc[45, df2.columns.get_loc("close")] *= 2.0  # mutate a FUTURE bar
    thr2 = rolling_pct_threshold(strat.feature_vol(df2), strat.comp_window, strat.comp_pct)
    assert thr1.iloc[40] == pytest.approx(thr2.iloc[40])


# ---- straddle payoff (the tautology guard) ----

def test_payoff_nets_to_minus_cost_at_fair_move():
    sigma_val, H, cost = 0.01, 4, 0.0006
    prem = _SQRT_2_OVER_PI * sigma_val * np.sqrt(H)
    closes = [100, 100, 100, 100, 100 * np.exp(prem), 100]  # i=0 -> i=4 move == prem
    df = _df_from_closes  # placeholder to keep linters calm
    idx = pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC")
    df = pd.DataFrame({"open": closes, "high": closes, "low": closes,
                       "close": closes, "volume": 1.0}, index=idx)
    signals = pd.Series([True] + [False] * 5, index=idx)
    sigma = pd.Series([sigma_val] * 6, index=idx)
    pay = straddle_payoffs(df, signals, sigma, horizons=(H,), cost=cost)
    assert pay.iloc[0]["net_4"] == pytest.approx(-cost, abs=1e-12)


def test_payoff_positive_when_expansion_beats_premium():
    sigma_val, H, cost = 0.01, 4, 0.0006
    prem = _SQRT_2_OVER_PI * sigma_val * np.sqrt(H)
    closes = [100, 100, 100, 100, 100 * np.exp(2 * prem), 100]  # move == 2*prem
    idx = pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC")
    df = pd.DataFrame({"open": closes, "high": closes, "low": closes,
                       "close": closes, "volume": 1.0}, index=idx)
    signals = pd.Series([True] + [False] * 5, index=idx)
    sigma = pd.Series([sigma_val] * 6, index=idx)
    pay = straddle_payoffs(df, signals, sigma, horizons=(H,), cost=cost)
    assert pay.iloc[0]["net_4"] == pytest.approx(prem - cost, abs=1e-12)
    assert pay.iloc[0]["net_4"] > 0


def test_right_edge_dropped():
    idx = pd.date_range("2020-01-01", periods=5, freq="h", tz="UTC")
    closes = [100, 101, 102, 103, 104]
    df = pd.DataFrame({"open": closes, "high": closes, "low": closes,
                       "close": closes, "volume": 1.0}, index=idx)
    signals = pd.Series([False, False, False, True, False], index=idx)  # i=3, no i+4
    sigma = pd.Series([0.01] * 5, index=idx)
    pay = straddle_payoffs(df, signals, sigma, horizons=(4,), cost=0.0006)
    assert np.isnan(pay.iloc[0]["net_4"])


# ---- bootstrap / verdict ----

def test_block_bootstrap_ci_non_degenerate_when_n_gt_block():
    r = np.random.default_rng(1).normal(0.001, 0.01, size=50)
    lo, hi = block_bootstrap_ci(r, block=20, n_boot=500, seed=0)
    assert hi > lo


def test_block_bootstrap_ci_empty_is_nan():
    lo, hi = block_bootstrap_ci(np.array([]))
    assert np.isnan(lo) and np.isnan(hi)


def test_verdict_branches():
    assert verdict({"n_signals": 40, "ci1d_lo": 0.001}, min_n=30) == "PASS"
    assert verdict({"n_signals": 40, "ci1d_lo": -0.001}, min_n=30) == "FAIL"
    assert verdict({"n_signals": 10, "ci1d_lo": 0.5}, min_n=30).startswith("UNDERPOWERED")


def test_slice_stats_keys():
    idx = pd.date_range("2020-01-01", periods=3, freq="h", tz="UTC")
    payoffs = pd.DataFrame({"entry_ts": idx, "net_24": [0.01, np.nan, -0.01],
                            "net_48": [0.02, 0.0, np.nan]})
    s = slice_stats(payoffs, 24, 48)
    for k in ["n_signals", "win_rate", "mean_net_1d", "mean_net_2d",
              "ci1d_lo", "ci1d_hi", "ci2d_lo", "ci2d_hi"]:
        assert k in s
    assert s["n_signals"] == 3  # count includes right-edge NaN rows


# ---- CLI smoke ----

def test_main_runs_and_prints_verdict(tmp_path, capsys):
    from vol_compression_backtest import main
    n = 1000
    base = pd.Timestamp("2020-01-01", tz="UTC")
    idx = pd.date_range(base, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 0.01, size=n)
    closes = 100.0 * np.exp(np.cumsum(rets))
    rows = [[int(idx[i].timestamp() * 1000), closes[i], closes[i], closes[i],
             closes[i], 1.0] for i in range(n)]
    p = tmp_path / "o.csv"
    pd.DataFrame(rows).to_csv(p, header=False, index=False)
    rc = main(["--ohlcv", str(p), "--start", "2020-01-01",
               "--oos-cutoff", "2020-01-20", "--comp-pct", "20"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "IN-SAMPLE" in out and "SEALED OOS" in out and "VERDICT" in out
