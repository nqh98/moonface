import numpy as np
import pandas as pd
import pytest

from capitulation_backtest import (
    CapitulationStrategy,
    block_bootstrap_ci,
    forward_log_returns,
    keltner_lower,
    load_data,
    main,
    rolling_pct_threshold,
    simulate_trades,
    slice_stats,
    verdict,
)


def _write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, header=False, index=False)


def test_load_data_ffills_funding_without_future_leak(tmp_path):
    base = pd.Timestamp("2020-01-01", tz="UTC")
    ohlcv = [
        [
            int((base + pd.Timedelta(hours=h)).timestamp() * 1000),
            100.0,
            101.0,
            99.0,
            100.0,
            50.0,
        ]
        for h in range(10)
    ]
    funding = [
        [int(base.timestamp() * 1000), 0.001],
        [int((base + pd.Timedelta(hours=8)).timestamp() * 1000), -0.002],
    ]
    op = tmp_path / "ohlcv.csv"
    fp = tmp_path / "funding.csv"
    _write_csv(op, ohlcv)
    _write_csv(fp, funding)

    df = load_data(str(op), str(fp))

    assert list(df.columns) == ["open", "high", "low", "close", "volume", "funding"]
    assert df.index.tz is not None
    assert df.iloc[3]["funding"] == pytest.approx(0.001)
    assert df.iloc[7]["funding"] == pytest.approx(0.001)
    assert df.iloc[8]["funding"] == pytest.approx(-0.002)
    assert np.allclose(df.iloc[:8]["funding"].to_numpy(), 0.001)


def _flat_df(n, price=100.0, vol=50.0):
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": vol,
            "funding": 0.0001,
        },
        index=idx,
    )


def test_keltner_lower_is_causal_no_future_leak():
    df = _flat_df(60)
    df.loc[df.index, "close"] = np.linspace(100, 110, 60)
    band_a = keltner_lower(df, ema_n=5, atr_n=5, mult=3.0)
    df2 = df.copy()
    df2.iloc[40, df2.columns.get_loc("close")] = 999.0
    band_b = keltner_lower(df2, ema_n=5, atr_n=5, mult=3.0)
    pd.testing.assert_series_equal(band_a.iloc[:41], band_b.iloc[:41])


def test_rolling_pct_threshold_excludes_current_bar():
    s = pd.Series([1, 2, 3, 4, 100.0])
    thr = rolling_pct_threshold(s, window=3, pct=95)
    assert thr.iloc[4] == pytest.approx(np.quantile([2, 3, 4], 0.95))


def _capit_df(n=780, spike_idx=(760,), extreme_funding=True):
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 100.0,
            "funding": 0.0001,
        },
        index=idx,
    )
    for si in spike_idx:
        df.iloc[si, df.columns.get_loc("open")] = 100.0
        df.iloc[si, df.columns.get_loc("high")] = 100.0
        df.iloc[si, df.columns.get_loc("low")] = 80.0
        df.iloc[si, df.columns.get_loc("close")] = 80.0
        df.iloc[si, df.columns.get_loc("volume")] = 1000.0
        df.iloc[si, df.columns.get_loc("funding")] = -0.01 if extreme_funding else 0.01
    return df


def _fast_strategy(**kw):
    params = dict(
        ema_period=5,
        atr_period=5,
        vol_window_days=1,
        funding_window_days=1,
        cooldown_bars=24,
    )
    params.update(kw)
    return CapitulationStrategy(**params)


def test_fires_exactly_once_on_capitulation_bar():
    df = _capit_df(spike_idx=(760,))
    sig = _fast_strategy().generate_signals(df)
    assert sig.sum() == 1
    assert bool(sig.iloc[760]) is True


def test_requires_all_three_conditions():
    df = _capit_df(spike_idx=(760,), extreme_funding=False)
    sig = _fast_strategy().generate_signals(df)
    assert sig.sum() == 0


def test_cooldown_suppresses_second_fire_within_window():
    df = _capit_df(spike_idx=(760, 770))
    sig = _fast_strategy(cooldown_bars=24).generate_signals(df)
    assert sig.sum() == 1
    assert bool(sig.iloc[760]) is True
    assert bool(sig.iloc[770]) is False


def _df_from_bars(bars):
    idx = pd.date_range("2020-01-01", periods=len(bars), freq="h", tz="UTC")
    return pd.DataFrame(
        bars,
        index=idx,
        columns=["open", "high", "low", "close", "volume", "funding"],
    )


def test_sl_first_same_bar_tie_is_loss():
    bars = [
        [100, 100, 100, 100, 1, 0.0],
        [100, 103, 98.9, 101, 1, 0.0],
    ]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False], index=df.index)
    trades = simulate_trades(df, sig, tp=0.02, sl=0.01, timeout_bars=48)
    assert len(trades) == 1
    assert trades.iloc[0]["outcome"] == "loss"


def test_clean_tp_is_win():
    bars = [
        [100, 100, 100, 100, 1, 0.0],
        [100, 102.5, 99.5, 102, 1, 0.0],
    ]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False], index=df.index)
    trades = simulate_trades(df, sig, tp=0.02, sl=0.01, timeout_bars=48)
    assert trades.iloc[0]["outcome"] == "win"


def test_timeout_scratch_win_and_loss():
    base = [100, 100.5, 99.5, 100, 1, 0.0]
    up = _df_from_bars([base, base, [100, 100.5, 99.5, 100.4, 1, 0.0]])
    down = _df_from_bars([base, base, [100, 100.5, 99.5, 99.6, 1, 0.0]])
    sig = pd.Series([True, False, False], index=up.index)
    t_up = simulate_trades(up, sig, tp=0.02, sl=0.01, timeout_bars=2)
    t_down = simulate_trades(down, sig, tp=0.02, sl=0.01, timeout_bars=2)
    assert t_up.iloc[0]["outcome"] == "scratch_win"
    assert t_down.iloc[0]["outcome"] == "scratch_loss"


def test_forward_log_returns_values_and_right_edge_drop():
    closes = [100, 101, 102, 103, 104, 105]
    bars = [[c, c, c, c, 1, 0.0] for c in closes]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False, False, False, True, False], index=df.index)
    out = forward_log_returns(df, sig, horizons=(2,))
    assert len(out[2]) == 1
    assert out[2][0] == pytest.approx(np.log(102 / 100))


def test_block_bootstrap_ci_positive_constant_excludes_zero():
    r = np.full(50, 0.01)
    lo, hi = block_bootstrap_ci(r, block=24, n_boot=1000, seed=0)
    assert lo > 0
    assert hi == pytest.approx(0.01, abs=1e-9)


def test_block_bootstrap_ci_empty_is_nan():
    lo, hi = block_bootstrap_ci(np.array([]), block=24)
    assert np.isnan(lo) and np.isnan(hi)


def test_verdict_pass_fail_underpowered():
    assert verdict({"n_signals": 30, "ci24_lo": 0.001}, min_n=20) == "PASS"
    assert verdict({"n_signals": 30, "ci24_lo": -0.001}, min_n=20) == "FAIL"
    assert verdict({"n_signals": 5, "ci24_lo": 0.5}, min_n=20).startswith(
        "UNDERPOWERED"
    )


def test_slice_stats_keys_and_winrate():
    df = _capit_df(spike_idx=(760,))
    stats = slice_stats(df, _fast_strategy())
    for k in [
        "n_signals",
        "win_rate",
        "mean_fwd_4h",
        "mean_fwd_24h",
        "ci24_lo",
        "ci24_hi",
    ]:
        assert k in stats
    assert stats["n_signals"] == 1


def test_main_runs_and_prints_verdict(tmp_path, capsys):
    n = 900
    base = pd.Timestamp("2020-01-01", tz="UTC")
    idx = pd.date_range(base, periods=n, freq="h", tz="UTC")
    ohlcv = [
        [int(idx[h].timestamp() * 1000), 100, 100, 100, 100, 100] for h in range(n)
    ]
    ohlcv[760] = [int(idx[760].timestamp() * 1000), 100, 100, 80, 80, 1000]
    funding = [
        [int(base.timestamp() * 1000), 0.0001],
        [int(idx[760].timestamp() * 1000), -0.01],
    ]
    op = tmp_path / "o.csv"
    fp = tmp_path / "f.csv"
    pd.DataFrame(ohlcv).to_csv(op, header=False, index=False)
    pd.DataFrame(funding).to_csv(fp, header=False, index=False)

    rc = main(
        [
            "--ohlcv",
            str(op),
            "--funding",
            str(fp),
            "--oos-cutoff",
            "2020-02-05",
            "--ema-period",
            "5",
            "--atr-period",
            "5",
            "--vol-window-days",
            "1",
            "--funding-window-days",
            "1",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "IN-SAMPLE" in out and "SEALED OOS" in out
    assert "VERDICT" in out
