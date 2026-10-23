# tests/test_engine_calibration_report.py
"""Pre-registered classification (spec §4c) + report assembly + degenerates."""
import math
import random

from moonface.core.models import Candle
from moonface.models.engine.calibration import (HypoTrade, build_report,
                                                classify_book,
                                                overall_verdict,
                                                split_summary)
from moonface.models.engine.config import EngineConfig, engine_hash

H = 3_600_000


def _trade(i, score, net_r, policy="ALLOW", direction=1, vol="normal"):
    return HypoTrade(entry_index=i * 10, exit_index=i * 10 + 1,
                     entry_ts_ms=i * 10 * H, exit_ts_ms=(i * 10 + 1) * H,
                     book="trend", direction=direction, score=score,
                     breadth=3, policy=policy, macro_effective="NEUTRAL",
                     vol_state=vol, net_r=net_r, bars_held=1,
                     exit_reason="test")


def _calibrated_fixture(n=400):
    # score in 0..100, net_r follows score with small deterministic wiggle;
    # >=60 count is ~40% of n -> both floors met; both halves positive rho.
    return [_trade(i, i % 101, (i % 101) / 100.0 + ((i % 7) - 3) * 0.01)
            for i in range(n)]


def test_classify_book_pass():
    trades = _calibrated_fixture()
    last_ts = trades[-1].entry_ts_ms
    out = classify_book(trades, first_ts=0, last_ts=last_ts)
    assert out["status"] == "pass"
    assert out["spearman_rho"] > 0.9
    assert out["rho_ci_95"][0] > 0
    assert out["buckets_weakly_increasing"] is True
    assert out["stability_sign_agrees"] is True
    assert out["events"] == 400
    assert out["events_score_ge_60"] >= 30


def test_classify_book_fail_on_inverted_score():
    trades = [_trade(i, i % 101, -(i % 101) / 100.0 + ((i % 7) - 3) * 0.01)
              for i in range(400)]
    out = classify_book(trades, first_ts=0, last_ts=trades[-1].entry_ts_ms)
    assert out["status"] == "fail"
    assert out["spearman_rho"] < 0


def test_classify_book_underpowered_beats_pass_and_fail():
    few = _calibrated_fixture(50)  # n < 200 -> underpowered even though rho>0
    out = classify_book(few, first_ts=0, last_ts=few[-1].entry_ts_ms)
    assert out["status"] == "underpowered"


def test_overall_verdict_matrix():
    assert overall_verdict("pass", "pass") == "CALIBRATED"
    assert overall_verdict("pass", "fail") == "PARTIALLY_CALIBRATED"
    assert overall_verdict("pass", "underpowered") == "PARTIALLY_CALIBRATED"
    assert overall_verdict("fail", "fail") == "UNCALIBRATED"
    assert overall_verdict("fail", "underpowered") == "UNCALIBRATED"
    assert overall_verdict("underpowered", "underpowered") == "UNDERPOWERED"


def test_split_summary_groups_and_means():
    trades = [_trade(0, 50, 1.0, policy="ALLOW"),
              _trade(1, 50, 0.0, policy="ALLOW"),
              _trade(2, 50, -1.0, policy="REJECT")]
    out = split_summary(trades, lambda t: t.policy or "NONE")
    assert out["ALLOW"] == {"n": 2, "mean_net_r": 0.5}
    assert out["REJECT"] == {"n": 1, "mean_net_r": -1.0}


def _walk_series(n, seed=7, start=100.0):
    rng = random.Random(seed)
    out, price = [], start
    for i in range(n):
        drift = rng.uniform(-1.0, 1.5)
        o = price
        c = max(1.0, price + drift)
        hi = max(o, c) + rng.uniform(0.0, 0.8)
        lo = min(o, c) - rng.uniform(0.0, 0.8)
        out.append(Candle(i * H, o, hi, lo, c, 10.0))
        price = c
    return out


def test_build_report_end_to_end_on_synthetic_series():
    candles = _walk_series(560, seed=11)
    cfg = EngineConfig(lookback_bars=400)
    report = build_report(cfg, candles, warmup=380)
    assert report["verdict"] in ("CALIBRATED", "PARTIALLY_CALIBRATED",
                                 "UNCALIBRATED", "UNDERPOWERED")
    assert set(report["books"]) == {"trend", "mean_revert"}
    for book in report["books"].values():
        assert "calibration" in book and "splits" in book
        assert "nonoverlapping" in book and "reversal_sensitivity" in book
        assert "panel_counts" in book
    assert len(report["module_ic_secondary"]) in (0, 12)
    # the report carries the hash of the config it ran under (the frozen
    # registration hash is pinned separately, on defaults, in the pass tests)
    assert report["engine_hash"] == engine_hash(cfg)
    assert "deriv=None" in " ".join(report["assumptions"])
    assert isinstance(report["data"]["fingerprint_sha256"], str)
    # small synthetic sample must be honestly underpowered, not opined on
    assert report["verdict"] == "UNDERPOWERED"


def test_build_report_empty_and_flat_inputs_are_safe():
    cfg = EngineConfig(lookback_bars=400)
    # fewer candles than warmup -> zero rows
    tiny = _walk_series(50)
    report = build_report(cfg, tiny, warmup=380)
    assert report["verdict"] == "UNDERPOWERED"
    # constant prices -> books never directional -> zero events
    flat = [Candle(i * H, 100.0, 100.0, 100.0, 100.0, 1.0)
            for i in range(450)]
    report2 = build_report(cfg, flat, warmup=420)
    assert report2["verdict"] == "UNDERPOWERED"
    assert report2["books"]["trend"]["panel_counts"]["events"] == 0
    assert not math.isnan(
        report2["data"]["first_scored_ts_ms"] or 0)
