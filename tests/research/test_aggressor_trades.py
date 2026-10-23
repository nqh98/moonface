import csv
import math
import tempfile
import unittest
from pathlib import Path

from moonface.research.aggressor_trades import (
    BUCKET_MS,
    LOCKBOX_FRACTION,
    REQUIRED_FIELDS,
    SecondBar,
    audit_trades,
    bucket_trades,
    evaluate_gate,
    load_trade_csv,
    render_report,
    run_nonlockbox_rung0,
    score_nonlockbox,
    spearman_ic,
    split_nonlockbox,
)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ts_ms", "symbol", "buy_count", "sell_count", "last_price"])
        writer.writeheader()
        writer.writerows(rows)


def second_bars(n_buckets, buy_fn, sell_fn, price_fn, symbol="BTCUSDT"):
    bars = []
    for b in range(n_buckets):
        for s in range(BUCKET_MS // 1000):
            i = b * (BUCKET_MS // 1000) + s
            bars.append(SecondBar(ts_ms=i * 1000, symbol=symbol,
                                  buy_count=buy_fn(i), sell_count=sell_fn(i),
                                  last_price=price_fn(b)))
    return bars


def direct_acf1(vals):
    m = len(vals)
    mu = sum(vals) / m
    den = sum((v - mu) ** 2 for v in vals)
    if den <= 0.0:
        return 0.0
    return sum((vals[t] - mu) * (vals[t + 1] - mu) for t in range(m - 1)) / den


class TestAggressorTradesCore(unittest.TestCase):
    def test_load_trade_csv_normalizes_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seconds.csv"
            write_csv(
                path,
                [
                    {"ts_ms": "1000", "symbol": " BTCUSDT ", "buy_count": "3",
                     "sell_count": "0", "last_price": "100.0"},
                    {"ts_ms": "2000", "symbol": "BTCUSDT", "buy_count": "0",
                     "sell_count": "2", "last_price": "101.0"},
                ],
            )

            rows = load_trade_csv(path)

        self.assertEqual(
            REQUIRED_FIELDS,
            ("ts_ms", "symbol", "buy_count", "sell_count", "last_price"))
        self.assertEqual(
            rows,
            [
                SecondBar(ts_ms=1000, symbol="BTCUSDT", buy_count=3,
                          sell_count=0, last_price=100.0),
                SecondBar(ts_ms=2000, symbol="BTCUSDT", buy_count=0,
                          sell_count=2, last_price=101.0),
            ],
        )

    def test_load_trade_csv_rejects_forbidden_missing_or_invalid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.csv"
            missing.write_text(
                "ts_ms,symbol,buy_count,sell_count\n1000,BTCUSDT,1,1\n")

            forbidden = Path(tmp) / "forbidden.csv"
            forbidden.write_text(
                "ts_ms,symbol,buy_count,sell_count,last_price,size\n"
                "1000,BTCUSDT,1,0,100,2.0\n")

            unaligned = Path(tmp) / "unaligned.csv"
            unaligned.write_text(
                "ts_ms,symbol,buy_count,sell_count,last_price\n"
                "1500,BTCUSDT,1,0,100\n")

            empty_row = Path(tmp) / "empty.csv"
            empty_row.write_text(
                "ts_ms,symbol,buy_count,sell_count,last_price\n"
                "1000,BTCUSDT,0,0,100\n")

            with self.assertRaisesRegex(ValueError, "missing required fields: last_price"):
                load_trade_csv(missing)
            with self.assertRaisesRegex(ValueError, "forbidden fields present: size"):
                load_trade_csv(forbidden)
            with self.assertRaisesRegex(ValueError, "second-aligned"):
                load_trade_csv(unaligned)
            with self.assertRaisesRegex(ValueError, "at least one print"):
                load_trade_csv(empty_row)

    def test_audit_trades_reproduces_readiness_constraints(self):
        day_ms = 86_400_000
        rows = [
            SecondBar(ts_ms=i * day_ms, symbol="BTCUSDT", buy_count=1,
                      sell_count=1, last_price=100.0 + i)
            for i in range(181)
        ]

        audit = audit_trades(rows, cadence_ms=day_ms)

        self.assertEqual(audit["status"], "ready")
        self.assertEqual(audit["failures"], [])
        self.assertEqual(audit["checks"]["symbols"], ["BTCUSDT"])
        self.assertGreaterEqual(audit["checks"]["history_days"], 180)

    def test_audit_trades_blocks_non_monotonic_duplicates_and_short_history(self):
        rows = [
            SecondBar(ts_ms=2_000, symbol="ETHUSDT", buy_count=1,
                      sell_count=0, last_price=100.0),
            SecondBar(ts_ms=1_000, symbol="ETHUSDT", buy_count=0,
                      sell_count=1, last_price=99.0),
            SecondBar(ts_ms=1_000, symbol="ETHUSDT", buy_count=1,
                      sell_count=0, last_price=99.5),
        ]

        audit = audit_trades(rows, cadence_ms=1_000)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("BTCUSDT coverage is required", audit["failures"])
        self.assertIn("history_days must be at least 180", audit["failures"])
        self.assertIn("timestamps must be monotonic", audit["failures"])
        self.assertIn("duplicate_timestamp_ratio must be <= 0.01", audit["failures"])


class TestAggressorTradesBuckets(unittest.TestCase):
    def test_clustered_sell_arrivals_yield_negative_excitation_asymmetry(self):
        bars = second_bars(
            3,
            buy_fn=lambda i: 1,
            sell_fn=lambda i: 4 if (i % 8) < 4 else 0,
            price_fn=lambda b: [100.0, 102.0, 105.0][b],
        )

        buckets = bucket_trades(bars, window_seconds=300)

        self.assertEqual(len(buckets), 2)
        self.assertEqual(buckets[0]["bucket_start_ms"], 0)
        self.assertLess(buckets[0]["excitation_asym"], 0.0)
        self.assertLess(buckets[1]["excitation_asym"], 0.0)
        self.assertAlmostEqual(buckets[0]["next_log_return"],
                               math.log(102.0 / 100.0))
        self.assertAlmostEqual(buckets[1]["next_log_return"],
                               math.log(105.0 / 102.0))

    def test_clustered_buy_arrivals_yield_positive_excitation_asymmetry(self):
        bars = second_bars(
            2,
            buy_fn=lambda i: 4 if (i % 8) < 4 else 0,
            sell_fn=lambda i: 1,
            price_fn=lambda b: [100.0, 101.0][b],
        )

        buckets = bucket_trades(bars, window_seconds=300)

        self.assertEqual(len(buckets), 1)
        self.assertGreater(buckets[0]["excitation_asym"], 0.0)

    def test_sliding_window_feature_matches_direct_acf1(self):
        buy = lambda i: (i * 7) % 5 + (1 if (i % 13) < 4 else 0)  # noqa: E731
        sell = lambda i: (i * 3) % 4  # noqa: E731
        bars = second_bars(2, buy_fn=buy, sell_fn=sell,
                           price_fn=lambda b: 100.0 + b)

        buckets = bucket_trades(bars, window_seconds=300)

        want = (direct_acf1([buy(i) for i in range(300)])
                - direct_acf1([sell(i) for i in range(300)]))
        self.assertEqual(len(buckets), 1)
        self.assertAlmostEqual(buckets[0]["excitation_asym"], want)

    def test_warmup_buckets_before_full_window_emit_nothing(self):
        bars = second_bars(
            3,
            buy_fn=lambda i: 1,
            sell_fn=lambda i: 4 if (i % 8) < 4 else 0,
            price_fn=lambda b: 100.0 + b,
        )

        buckets = bucket_trades(bars, window_seconds=600)

        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["bucket_start_ms"], BUCKET_MS)

    def test_split_nonlockbox_seals_final_twenty_percent(self):
        buckets = [
            {"bucket_start_ms": i * BUCKET_MS, "excitation_asym": 0.1,
             "next_log_return": 0.001}
            for i in range(10)
        ]

        dev, lockbox = split_nonlockbox(buckets)

        self.assertEqual(len(dev), 8)
        self.assertEqual(len(lockbox), 2)
        self.assertEqual(lockbox[0]["bucket_start_ms"], 8 * BUCKET_MS)
        self.assertEqual(LOCKBOX_FRACTION, 0.20)


class TestAggressorTradesStats(unittest.TestCase):
    def test_spearman_ic_is_positive_for_monotone_relationship(self):
        self.assertAlmostEqual(
            spearman_ic([0.1, 0.2, 0.3, 0.4], [0.01, 0.02, 0.03, 0.04]),
            1.0,
        )
        self.assertAlmostEqual(
            spearman_ic([0.1, 0.2, 0.3, 0.4], [0.04, 0.03, 0.02, 0.01]),
            -1.0,
        )

    def test_score_nonlockbox_uses_six_chronological_folds(self):
        buckets = []
        for i in range(60):
            x = (i % 10) / 10.0
            buckets.append(
                {
                    "bucket_start_ms": i * BUCKET_MS,
                    "excitation_asym": x,
                    "next_log_return": x * 0.01 + x * x * 0.001,
                    "total_count": 10.0 + i,
                }
            )

        score = score_nonlockbox(buckets, folds=6)

        self.assertEqual(score["fold_count"], 6)
        self.assertEqual(score["positive_fold_count"], 6)
        self.assertGreater(score["median_spearman_ic"], 0.015)
        self.assertGreaterEqual(score["newey_west_t"], 2.0)
        self.assertTrue(score["monotonic_bucket_check"])
        self.assertEqual(score["lockbox_touched"], False)

    def test_gate_blocks_failed_nonlockbox_score(self):
        score = {
            "fold_count": 6,
            "fold_spearman_ic": [-0.1, -0.1, 0.02, -0.03, 0.01, -0.02],
            "positive_fold_count": 2,
            "median_spearman_ic": -0.02,
            "newey_west_t": 0.4,
            "monotonic_bucket_check": False,
            "trimmed_effect_positive": False,
            "lockbox_touched": False,
        }

        verdict = evaluate_gate(score)

        self.assertEqual(verdict["status"], "killed")
        self.assertIn("median fold Spearman IC must be > 0.015", verdict["failures"])
        self.assertIn("at least two-thirds of folds must be positive", verdict["failures"])
        self.assertIn("Newey-West t-statistic must be >= 2.0", verdict["failures"])
        self.assertIn(
            "highest excitation-asymmetry bucket must beat lowest excitation-asymmetry bucket",
            verdict["failures"])


class TestAggressorTradesReport(unittest.TestCase):
    def test_run_nonlockbox_rung0_renders_guardrailed_report(self):
        rows = [
            SecondBar(ts_ms=i * BUCKET_MS, symbol="BTCUSDT",
                      buy_count=2 if i % 2 == 0 else 1,
                      sell_count=1 if i % 2 == 0 else 2,
                      last_price=100.0 + i)
            for i in range(240)
        ]

        result = run_nonlockbox_rung0(rows, cadence_ms=BUCKET_MS)
        report = render_report(result)

        self.assertIn(result["verdict"]["status"], {"nonlockbox_pass", "killed"})
        self.assertEqual(result["lockbox_touched"], False)
        self.assertIn("No strategy backtest was run.", report)
        self.assertIn("lockbox_touched: false", report)
        self.assertIn("This is not a trading result.", report)
        self.assertIn("excitation asymmetry", report)
