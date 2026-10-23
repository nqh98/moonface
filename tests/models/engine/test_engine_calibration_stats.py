# tests/test_engine_calibration_stats.py
"""Stdlib statistics for the calibration diagnostic (no numpy)."""
import math

from moonface.core.models import Candle
from moonface.models.engine.calibration import (BarRow, BookState, HypoTrade,
                                                block_bootstrap_rho_ci,
                                                bucket_stats,
                                                buckets_weakly_increasing,
                                                module_ic_table,
                                                nw_tstat_of_mean, spearman)

H = 3_600_000


def _trade(i, score, net_r, entry_index=None):
    idx = entry_index if entry_index is not None else i
    return HypoTrade(entry_index=idx, exit_index=idx + 1,
                     entry_ts_ms=idx * H, exit_ts_ms=(idx + 1) * H,
                     book="trend", direction=1, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=1,
                     exit_reason="test")


def test_spearman_perfect_monotone_and_inverse():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert spearman(xs, [2.0, 4.0, 6.0, 8.0, 10.0]) == 1.0
    assert spearman(xs, [10.0, 8.0, 6.0, 4.0, 2.0]) == -1.0


def test_spearman_degenerate_returns_none():
    assert spearman([1.0, 2.0], [1.0, 2.0]) is None          # n < 3
    assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # constant side


def test_spearman_handles_ties_via_average_ranks():
    # xs ties: ranks [1, 2.5, 2.5, 4]
    rho = spearman([10.0, 20.0, 20.0, 30.0], [1.0, 2.0, 3.0, 4.0])
    assert rho is not None and 0.9 < rho <= 1.0


def test_bucket_stats_edges_and_means():
    trades = [_trade(0, 10, -1.0), _trade(1, 39, -1.0),   # <40
              _trade(2, 40, 0.0), _trade(3, 59, 0.2),     # 40-59
              _trade(4, 60, 0.5),                          # 60-74
              _trade(5, 75, 1.0), _trade(6, 100, 2.0)]     # >=75
    b = bucket_stats(trades)
    assert [x["n"] for x in b] == [2, 2, 1, 2]
    assert b[0]["mean_net_r"] == -1.0
    assert b[1]["mean_net_r"] == 0.1
    assert b[2]["mean_net_r"] == 0.5
    assert b[3]["mean_net_r"] == 1.5
    assert buckets_weakly_increasing(b) is True


def test_buckets_weakly_increasing_skips_empty_and_detects_decrease():
    inc = [{"bucket": "a", "n": 1, "mean_net_r": 0.0},
           {"bucket": "b", "n": 0, "mean_net_r": None},
           {"bucket": "c", "n": 1, "mean_net_r": 0.5}]
    dec = [{"bucket": "a", "n": 1, "mean_net_r": 0.5},
           {"bucket": "b", "n": 1, "mean_net_r": 0.0}]
    assert buckets_weakly_increasing(inc) is True
    assert buckets_weakly_increasing(dec) is False


def test_block_bootstrap_ci_positive_for_calibrated_fixture():
    # 400 events spread over many 168-bar blocks; net_r tracks score with a
    # small deterministic wiggle -> rho ~ 1, CI must exclude 0 from below.
    trades = [_trade(i, i % 101, (i % 101) / 100.0 + ((i % 7) - 3) * 0.01,
                     entry_index=i * 10) for i in range(400)]
    ci = block_bootstrap_rho_ci(trades)
    assert ci is not None
    assert ci[0] > 0


def test_block_bootstrap_ci_straddles_zero_for_unrelated_fixture():
    # net_r cycles independently of score -> rho ~ 0.
    trades = [_trade(i, i % 101, math.sin(i * 1.7), entry_index=i * 10)
              for i in range(400)]
    ci = block_bootstrap_rho_ci(trades)
    assert ci is not None
    assert ci[0] < 0 < ci[1]


def test_block_bootstrap_needs_two_blocks():
    trades = [_trade(i, i, 0.1, entry_index=i) for i in range(5)]  # 1 block
    assert block_bootstrap_rho_ci(trades) is None


def test_nw_tstat_of_mean():
    strong = [1.0 + 0.01 * (i % 3) for i in range(300)]
    weak = [(-1.0) ** i for i in range(300)]
    t_strong = nw_tstat_of_mean(strong)
    t_weak = nw_tstat_of_mean(weak)
    assert t_strong is not None and t_strong > 10
    assert t_weak is not None and abs(t_weak) < 2
    assert nw_tstat_of_mean([1.0] * 10) is None  # n < lag+2


def _row(index, points):
    return BarRow(index=index, ts_ms=index * H, macro_effective="NEUTRAL",
                  vol_state="normal", regime_trend=0,
                  trend=BookState(0, 0, 0, None),
                  revert=BookState(0, 0, 0, None),
                  module_points=points, sweep_wick=None,
                  decision_action="WAIT", decision_direction=0,
                  decision_score=0)


def test_module_ic_table_finds_predictive_module():
    # close rises while m2_breakout is +1 (first half) and falls while it is
    # -1 (second half), so 24-bar forward returns track the module. The signal
    # regime must be much longer than the horizon: with 24-bar blocks every
    # forward window straddles two opposite blocks and the true IC is ~0.1.
    n = 400
    signal = [1 if i < 200 else -1 for i in range(n)]
    closes = [100.0]
    for i in range(1, n + 30):
        prev_sig = signal[i - 1] if 0 <= i - 1 < n else 0
        closes.append(closes[-1] * (1.0 + 0.001 * prev_sig))
    candles = [Candle(i * H, c, c, c, c, 1.0) for i, c in enumerate(closes)]
    rows = [_row(i, {"m2_breakout": 20 * signal[i], "m1_macro": 0})
            for i in range(n)]
    table = module_ic_table(rows, candles)
    by_name = {e["module"]: e for e in table}
    assert by_name["m2_breakout"]["rank_ic"] is not None
    assert by_name["m2_breakout"]["rank_ic"] > 0.5
    assert by_name["m1_macro"]["rank_ic"] is None  # constant zero -> None


def test_module_ic_table_empty_rows_is_safe():
    assert module_ic_table([], []) == []
