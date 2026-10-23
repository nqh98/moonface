import numpy as np
import pandas as pd
import pytest

from session_sweeps_backtest import (
    SessionSweepStrategy,
    block_bootstrap_ci,
    load_data,
    main,
    slice_stats,
    signed_forward_returns,
    tag_sessions,
    verdict,
)


def test_load_data_parses_utc_and_slices(tmp_path):
    base = pd.Timestamp("2020-01-01", tz="UTC")
    rows = [[int((base + pd.Timedelta(minutes=15 * h)).timestamp() * 1000),
             100.0, 101.0, 99.0, 100.0, 5.0] for h in range(10)]
    p = tmp_path / "ohlcv.csv"
    pd.DataFrame(rows).to_csv(p, header=False, index=False)

    df = load_data(str(p))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None
    assert len(df) == 10
    assert df.index.is_monotonic_increasing


def _df(idx, ohlc):
    return pd.DataFrame(
        ohlc,
        index=idx,
        columns=["open", "high", "low", "close", "volume"],
    )


def test_session_ids_and_keys():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 03:00", tz="UTC"),
        pd.Timestamp("2020-01-01 10:00", tz="UTC"),
        pd.Timestamp("2020-01-01 18:00", tz="UTC"),
        pd.Timestamp("2020-01-02 01:00", tz="UTC"),
    ])
    df = _df(idx, [[1, 1, 1, 1, 1]] * 4)
    t = tag_sessions(df)
    assert list(t["session_id"]) == [0, 1, 2, 0]
    assert list(t["session_key"]) == [0, 1, 2, 3]


def test_prior_level_from_previous_block():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 00:00", tz="UTC"),
        pd.Timestamp("2020-01-01 04:00", tz="UTC"),
        pd.Timestamp("2020-01-01 08:00", tz="UTC"),
    ])
    df = _df(
        idx,
        [
            [100, 105, 97, 100, 1],
            [100, 103, 95, 100, 1],
            [100, 101, 99, 100, 1],
        ],
    )
    t = tag_sessions(df)
    assert np.isnan(t.iloc[0]["prior_high"])
    assert t.iloc[2]["prior_high"] == 105
    assert t.iloc[2]["prior_low"] == 95


def test_prior_level_no_future_leak():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 00:00", tz="UTC"),
        pd.Timestamp("2020-01-01 08:00", tz="UTC"),
        pd.Timestamp("2020-01-01 16:00", tz="UTC"),
    ])
    base = [
        [100, 110, 90, 100, 1],
        [100, 101, 85, 95, 1],
        [100, 200, 50, 100, 1],
    ]
    t1 = tag_sessions(_df(idx, base))
    mutated = [row[:] for row in base]
    mutated[2] = [100, 999, 1, 100, 1]
    t2 = tag_sessions(_df(idx, mutated))
    assert t1.iloc[1]["prior_high"] == t2.iloc[1]["prior_high"]
    assert t1.iloc[1]["prior_low"] == t2.iloc[1]["prior_low"]


def _two_block_df(trigger, filler=None):
    """Block0 sets prior levels; block1 contains the trigger bar."""
    rows = [[100, 110, 90, 100, 1], trigger]
    times = [
        pd.Timestamp("2020-01-01 00:00", tz="UTC"),
        pd.Timestamp("2020-01-01 08:00", tz="UTC"),
    ]
    if filler is not None:
        rows.append(filler)
        times.append(pd.Timestamp("2020-01-01 08:15", tz="UTC"))
    return tag_sessions(_df(pd.DatetimeIndex(times), rows))


def test_reversal_fires_long():
    df = _two_block_df([100, 101, 85, 95, 1])
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["direction"] == 1
    assert sig.iloc[0]["entry_price"] == 95


def test_reversal_fires_short():
    df = _two_block_df([100, 115, 99, 105, 1])
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["direction"] == -1


def test_clean_breakout_no_reversal_but_continuation():
    df = _two_block_df([100, 116, 100, 113, 1])
    assert len(SessionSweepStrategy(mode="reversal").generate_signals(df)) == 0
    csig = SessionSweepStrategy(mode="continuation").generate_signals(df)
    assert len(csig) == 1
    assert csig.iloc[0]["direction"] == 1


def test_first_per_session_dedup():
    df = _two_block_df([100, 101, 85, 95, 1], filler=[100, 101, 80, 96, 1])
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["entry_ts"] == pd.Timestamp("2020-01-01 08:00", tz="UTC")


def test_signed_forward_returns_sign_and_right_edge():
    idx = pd.date_range("2020-01-01", periods=5, freq="15min", tz="UTC")
    df = _df(idx, [[100, 100, 100, c, 1] for c in [100, 101, 102, 103, 104]])
    long_sig = pd.DataFrame([
        {"entry_ts": idx[0], "entry_price": 100, "direction": 1},
        {"entry_ts": idx[4], "entry_price": 104, "direction": 1},
    ])
    out = signed_forward_returns(df, long_sig, horizons=(2,))
    assert len(out[2]) == 1
    assert out[2][0] == pytest.approx(np.log(102 / 100))

    short_sig = pd.DataFrame([
        {"entry_ts": idx[0], "entry_price": 100, "direction": -1},
    ])
    outs = signed_forward_returns(df, short_sig, horizons=(2,))
    assert outs[2][0] == pytest.approx(-np.log(102 / 100))


def test_block_bootstrap_ci_non_degenerate_when_n_gt_block():
    rng = np.random.default_rng(1)
    returns = rng.normal(0.001, 0.01, size=50)
    lo, hi = block_bootstrap_ci(returns, block=20, n_boot=500, seed=0)
    assert hi > lo


def test_block_bootstrap_ci_empty_is_nan():
    lo, hi = block_bootstrap_ci(np.array([]), block=20)
    assert np.isnan(lo) and np.isnan(hi)


def test_verdict_branches():
    assert verdict({"n_signals": 40, "ci4_lo": 0.001}, min_n=30) == "PASS"
    assert verdict({"n_signals": 40, "ci4_lo": -0.001}, min_n=30) == "FAIL"
    assert verdict({"n_signals": 10, "ci4_lo": 0.5}, min_n=30).startswith(
        "UNDERPOWERED"
    )


def test_slice_stats_keys_and_count():
    df = _two_block_df([100, 101, 85, 95, 1])
    stats = slice_stats(df, SessionSweepStrategy())
    for key in [
        "n_signals",
        "win_rate",
        "mean_fwd_2h",
        "mean_fwd_4h",
        "ci2_lo",
        "ci2_hi",
        "ci4_lo",
        "ci4_hi",
    ]:
        assert key in stats
    assert stats["n_signals"] == 1


def test_main_runs_and_prints_verdict(tmp_path, capsys):
    n_rows = 200
    base = pd.Timestamp("2020-01-01", tz="UTC")
    idx = pd.date_range(base, periods=n_rows, freq="15min", tz="UTC")
    rows = [
        [int(idx[i].timestamp() * 1000), 100, 100, 100, 100, 1]
        for i in range(n_rows)
    ]
    path = tmp_path / "o.csv"
    pd.DataFrame(rows).to_csv(path, header=False, index=False)

    rc = main(["--ohlcv", str(path), "--start", "2020-01-01", "--oos-cutoff", "2020-01-02"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "IN-SAMPLE" in out and "SEALED OOS" in out and "VERDICT" in out
