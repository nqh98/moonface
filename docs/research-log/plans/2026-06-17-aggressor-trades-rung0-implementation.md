# Aggressor Trades Rung-0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Rung-0 aggressor-trades information-test tooling without running the real provider experiment or touching the lockbox.

**Architecture:** Add one focused research module for CSV ingestion, readiness re-audit, 5-minute bucket construction, chronological non-lockbox fold scoring, fixed gate evaluation, and markdown/JSON report rendering. Add a thin CLI that writes artifacts only when explicitly pointed at a trade CSV and refuses lockbox evaluation unless a future explicit flag is introduced in a separate approved plan. Tests use synthetic in-memory/tempfile data only.

**Tech Stack:** Python stdlib, `pytest`, existing `tools/` CLI pattern, frozen preregistration at `experiments/newdata/AGGRESSOR_TRADES_RUNG0_PREREGISTRATION.md`.

---

## Non-Negotiable Constraints

- Do not run the real provider dataset.
- Do not run signal tests, return tests on real data, strategy backtests, sealed experiments, or lockbox evaluation.
- Use only `aggressor_trades` fields: `ts_ms`, `symbol`, `side`, `price`, `size`.
- Price is allowed only for the fixed next-bucket return label.
- No alternate horizons, bucket sizes, feature families, thresholds, filters, or parameter search.
- All implementation tests must use synthetic fixtures embedded in tests or temporary files.

## File Structure

- Create `src/moonface/research/aggressor_trades.py`: pure functions for parsing, audit, bucketization, non-lockbox split, fixed Rung-0 statistics, gate evaluation, and report rendering.
- Create `tools/aggressor_trades_rung0.py`: CLI wrapper around the pure module; writes `audit.json`, `nonlockbox_results.json`, and `report.md`.
- Create `tests/test_aggressor_trades.py`: unit tests for parsing, audit failures, bucket construction, lockbox split, statistics, gate/kill behavior, and report guardrails.
- Create `tests/test_aggressor_trades_cli.py`: CLI tests that use synthetic temp CSV data and assert one-touch artifact behavior.
- Do not modify the frozen preregistration except in a separate human-approved preregistration amendment.

## Task 1: Core Types, CSV Loading, And Ingestion Audit

**Files:**
- Create: `src/moonface/research/aggressor_trades.py`
- Test: `tests/test_aggressor_trades.py`

- [ ] **Step 1: Write failing tests for CSV loading and audit validation**

Create `tests/test_aggressor_trades.py`:

```python
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from moonface.research.aggressor_trades import (
    REQUIRED_FIELDS,
    TradePrint,
    audit_trades,
    load_trade_csv,
)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ts_ms", "symbol", "side", "price", "size"])
        writer.writeheader()
        writer.writerows(rows)


class TestAggressorTradesCore(unittest.TestCase):
    def test_load_trade_csv_normalizes_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.csv"
            write_csv(
                path,
                [
                    {"ts_ms": "1000", "symbol": "BTCUSDT", "side": "BUY", "price": "100.0", "size": "2.5"},
                    {"ts_ms": "2000", "symbol": "BTCUSDT", "side": "sell", "price": "101.0", "size": "1.0"},
                ],
            )

            trades = load_trade_csv(path)

        self.assertEqual(REQUIRED_FIELDS, ("ts_ms", "symbol", "side", "price", "size"))
        self.assertEqual(
            trades,
            [
                TradePrint(ts_ms=1000, symbol="BTCUSDT", side="buy", price=100.0, size=2.5),
                TradePrint(ts_ms=2000, symbol="BTCUSDT", side="sell", price=101.0, size=1.0),
            ],
        )

    def test_load_trade_csv_rejects_forbidden_or_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.csv"
            missing.write_text("ts_ms,symbol,side,price\n1000,BTCUSDT,buy,100\n")

            forbidden = Path(tmp) / "forbidden.csv"
            forbidden.write_text(
                "ts_ms,symbol,side,price,size,funding\n"
                "1000,BTCUSDT,buy,100,1,0.01\n"
            )

            with self.assertRaisesRegex(ValueError, "missing required fields: size"):
                load_trade_csv(missing)
            with self.assertRaisesRegex(ValueError, "forbidden fields present: funding"):
                load_trade_csv(forbidden)

    def test_audit_trades_reproduces_readiness_constraints(self):
        day_ms = 86_400_000
        trades = [
            TradePrint(ts_ms=i * day_ms, symbol="BTCUSDT", side="buy", price=100.0 + i, size=1.0)
            for i in range(181)
        ]

        audit = audit_trades(trades, cadence_ms=day_ms)

        self.assertEqual(audit["status"], "ready")
        self.assertEqual(audit["failures"], [])
        self.assertEqual(audit["checks"]["symbols"], ["BTCUSDT"])
        self.assertGreaterEqual(audit["checks"]["history_days"], 180)

    def test_audit_trades_blocks_non_monotonic_duplicates_and_short_history(self):
        trades = [
            TradePrint(ts_ms=2_000, symbol="ETHUSDT", side="buy", price=100.0, size=1.0),
            TradePrint(ts_ms=1_000, symbol="ETHUSDT", side="sell", price=99.0, size=1.0),
            TradePrint(ts_ms=1_000, symbol="ETHUSDT", side="buy", price=99.5, size=1.0),
        ]

        audit = audit_trades(trades, cadence_ms=1_000)

        self.assertEqual(audit["status"], "blocked")
        self.assertIn("BTCUSDT coverage is required", audit["failures"])
        self.assertIn("history_days must be at least 180", audit["failures"])
        self.assertIn("timestamps must be monotonic", audit["failures"])
        self.assertIn("duplicate_timestamp_ratio must be <= 0.01", audit["failures"])
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: import failure for `moonface.research.aggressor_trades`.

- [ ] **Step 3: Implement loader and audit core**

Create `src/moonface/research/aggressor_trades.py`:

```python
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

REQUIRED_FIELDS = ("ts_ms", "symbol", "side", "price", "size")
FORBIDDEN_FIELDS = {
    "return",
    "returns",
    "label",
    "target",
    "alpha",
    "score",
    "funding",
    "basis",
    "open_interest",
    "oi",
    "bid_prices",
    "ask_prices",
    "liquidation",
}
BUCKET_MS = 300_000
HORIZON_BUCKETS = 1
LOCKBOX_FRACTION = 0.20
MIN_HISTORY_DAYS = 180
MIN_COVERAGE_RATIO = 0.95
MAX_DUPLICATE_TS_RATIO = 0.01


@dataclass(frozen=True)
class TradePrint:
    ts_ms: int
    symbol: str
    side: str
    price: float
    size: float


def load_trade_csv(path: Path) -> list[TradePrint]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_FIELDS if name not in fieldnames]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        forbidden = sorted(set(fieldnames) & FORBIDDEN_FIELDS)
        if forbidden:
            raise ValueError(f"forbidden fields present: {', '.join(forbidden)}")

        trades: list[TradePrint] = []
        for row in reader:
            side = row["side"].strip().lower()
            if side not in {"buy", "sell"}:
                raise ValueError(f"side must be buy or sell, got {row['side']!r}")
            price = float(row["price"])
            size = float(row["size"])
            if price <= 0.0:
                raise ValueError("price must be positive")
            if size <= 0.0:
                raise ValueError("size must be positive")
            trades.append(
                TradePrint(
                    ts_ms=int(row["ts_ms"]),
                    symbol=row["symbol"].strip(),
                    side=side,
                    price=price,
                    size=size,
                )
            )
        return trades


def audit_trades(trades: list[TradePrint], *, cadence_ms: int) -> dict[str, Any]:
    failures: list[str] = []
    symbols = sorted({trade.symbol for trade in trades})
    timestamps = [trade.ts_ms for trade in trades]
    unique_timestamps = set(timestamps)
    duplicate_ratio = 1.0 if not timestamps else 1.0 - (len(unique_timestamps) / len(timestamps))
    monotonic = all(a <= b for a, b in zip(timestamps, timestamps[1:]))

    if "BTCUSDT" not in symbols:
        failures.append("BTCUSDT coverage is required")
    if not timestamps:
        history_days = 0
        coverage_ratio = 0.0
    else:
        history_days = int((max(timestamps) - min(timestamps)) / 86_400_000) + 1
        expected_points = max(1, int((max(timestamps) - min(timestamps)) / cadence_ms) + 1)
        coverage_ratio = min(1.0, len(unique_timestamps) / expected_points)
    if history_days < MIN_HISTORY_DAYS:
        failures.append("history_days must be at least 180")
    if coverage_ratio < MIN_COVERAGE_RATIO:
        failures.append("coverage_ratio must be at least 0.95")
    if not monotonic:
        failures.append("timestamps must be monotonic")
    if duplicate_ratio > MAX_DUPLICATE_TS_RATIO:
        failures.append("duplicate_timestamp_ratio must be <= 0.01")

    return {
        "status": "ready" if not failures else "blocked",
        "failures": failures,
        "checks": {
            "symbols": symbols,
            "history_days": history_days,
            "cadence_ms": cadence_ms,
            "coverage_ratio": coverage_ratio,
            "monotonic_timestamps": monotonic,
            "duplicate_timestamp_ratio": duplicate_ratio,
            "fields": list(REQUIRED_FIELDS),
        },
    }
```

- [ ] **Step 4: Run tests and verify Task 1 passes**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
rtk git add src/moonface/research/aggressor_trades.py tests/test_aggressor_trades.py
rtk git commit -m "feat(newdata): add aggressor trades ingestion audit"
```

## Task 2: Fixed 5-Minute Buckets And Lockbox Split

**Files:**
- Modify: `src/moonface/research/aggressor_trades.py`
- Test: `tests/test_aggressor_trades.py`

- [ ] **Step 1: Add failing tests for bucket construction and sealed-tail split**

Append to `tests/test_aggressor_trades.py`:

```python
from moonface.research.aggressor_trades import (
    BUCKET_MS,
    LOCKBOX_FRACTION,
    bucket_trades,
    split_nonlockbox,
)


class TestAggressorTradesBuckets(unittest.TestCase):
    def test_bucket_trades_builds_fixed_imbalance_and_next_return(self):
        trades = [
            TradePrint(ts_ms=0, symbol="BTCUSDT", side="buy", price=100.0, size=3.0),
            TradePrint(ts_ms=60_000, symbol="BTCUSDT", side="sell", price=101.0, size=1.0),
            TradePrint(ts_ms=BUCKET_MS, symbol="BTCUSDT", side="sell", price=102.0, size=2.0),
            TradePrint(ts_ms=BUCKET_MS + 60_000, symbol="BTCUSDT", side="sell", price=103.0, size=2.0),
            TradePrint(ts_ms=2 * BUCKET_MS, symbol="BTCUSDT", side="buy", price=106.0, size=1.0),
        ]

        buckets = bucket_trades(trades)

        self.assertEqual(len(buckets), 2)
        self.assertEqual(buckets[0]["bucket_start_ms"], 0)
        self.assertAlmostEqual(buckets[0]["imbalance"], 0.5)
        self.assertAlmostEqual(buckets[0]["next_log_return"], math.log(103.0 / 101.0))
        self.assertEqual(buckets[1]["bucket_start_ms"], BUCKET_MS)
        self.assertAlmostEqual(buckets[1]["imbalance"], -1.0)
        self.assertAlmostEqual(buckets[1]["next_log_return"], math.log(106.0 / 103.0))

    def test_split_nonlockbox_seals_final_twenty_percent(self):
        buckets = [
            {"bucket_start_ms": i * BUCKET_MS, "imbalance": 0.1, "next_log_return": 0.001}
            for i in range(10)
        ]

        dev, lockbox = split_nonlockbox(buckets)

        self.assertEqual(len(dev), 8)
        self.assertEqual(len(lockbox), 2)
        self.assertEqual(lockbox[0]["bucket_start_ms"], 8 * BUCKET_MS)
        self.assertEqual(LOCKBOX_FRACTION, 0.20)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: import failure for `bucket_trades` or `split_nonlockbox`.

- [ ] **Step 3: Implement bucket construction and lockbox split**

Append to `src/moonface/research/aggressor_trades.py`:

```python
def bucket_trades(trades: list[TradePrint]) -> list[dict[str, float]]:
    if not trades:
        return []
    ordered = sorted(trades, key=lambda trade: trade.ts_ms)
    grouped: dict[int, dict[str, float]] = {}
    first_bucket = (ordered[0].ts_ms // BUCKET_MS) * BUCKET_MS
    for trade in ordered:
        start = ((trade.ts_ms - first_bucket) // BUCKET_MS) * BUCKET_MS + first_bucket
        bucket = grouped.setdefault(
            start,
            {"bucket_start_ms": float(start), "buy_volume": 0.0, "sell_volume": 0.0, "last_price": trade.price},
        )
        if trade.side == "buy":
            bucket["buy_volume"] += trade.size
        else:
            bucket["sell_volume"] += trade.size
        bucket["last_price"] = trade.price

    rows = [grouped[start] for start in sorted(grouped)]
    buckets: list[dict[str, float]] = []
    for idx, row in enumerate(rows[:-HORIZON_BUCKETS]):
        total = row["buy_volume"] + row["sell_volume"]
        if total <= 0.0:
            continue
        next_row = rows[idx + HORIZON_BUCKETS]
        buckets.append(
            {
                "bucket_start_ms": int(row["bucket_start_ms"]),
                "buy_volume": row["buy_volume"],
                "sell_volume": row["sell_volume"],
                "total_volume": total,
                "imbalance": (row["buy_volume"] - row["sell_volume"]) / total,
                "last_price": row["last_price"],
                "next_log_return": math.log(next_row["last_price"] / row["last_price"]),
            }
        )
    return buckets


def split_nonlockbox(buckets: list[dict[str, float]]) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    fence = int(len(buckets) * (1.0 - LOCKBOX_FRACTION))
    return buckets[:fence], buckets[fence:]
```

- [ ] **Step 4: Run tests and verify Task 2 passes**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
rtk git add src/moonface/research/aggressor_trades.py tests/test_aggressor_trades.py
rtk git commit -m "feat(newdata): build fixed aggressor trade buckets"
```

## Task 3: Non-Lockbox Statistics And Gate Evaluation

**Files:**
- Modify: `src/moonface/research/aggressor_trades.py`
- Test: `tests/test_aggressor_trades.py`

- [ ] **Step 1: Add failing tests for fixed statistics and gate behavior**

Append to `tests/test_aggressor_trades.py`:

```python
from moonface.research.aggressor_trades import (
    evaluate_gate,
    score_nonlockbox,
    spearman_ic,
)


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
                    "imbalance": x,
                    "next_log_return": x * 0.01,
                    "total_volume": 10.0 + i,
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: import failure for `score_nonlockbox`, `spearman_ic`, or `evaluate_gate`.

- [ ] **Step 3: Implement statistics and fixed gate**

Append to `src/moonface/research/aggressor_trades.py`:

```python
def _ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = rank
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def spearman_ic(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


def _newey_west_t(xs: list[float], ys: list[float], *, lag: int = 5) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x <= 0.0:
        return 0.0
    beta = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    alpha = mean_y - beta * mean_x
    residuals = [y - alpha - beta * x for x, y in zip(xs, ys)]
    z = [(x - mean_x) * e for x, e in zip(xs, residuals)]
    gamma0 = sum(v * v for v in z) / n
    variance = gamma0
    max_lag = min(lag, n - 1)
    for ell in range(1, max_lag + 1):
        weight = 1.0 - ell / (max_lag + 1.0)
        gamma = sum(z[t] * z[t - ell] for t in range(ell, n)) / n
        variance += 2.0 * weight * gamma
    denom = math.sqrt(max(variance, 0.0) / n) / (var_x / n)
    return 0.0 if denom <= 0.0 else beta / denom


def _bucket_monotonic_check(rows: list[dict[str, float]]) -> bool:
    ordered = sorted(rows, key=lambda row: row["imbalance"])
    if len(ordered) < 5:
        return False
    chunk = len(ordered) // 5
    low = ordered[:chunk]
    high = ordered[-chunk:]
    low_mean = sum(row["next_log_return"] for row in low) / len(low)
    high_mean = sum(row["next_log_return"] for row in high) / len(high)
    return high_mean > low_mean


def _trimmed_effect_positive(rows: list[dict[str, float]]) -> bool:
    if len(rows) < 10:
        return False
    keep = max(1, int(len(rows) * 0.99))
    trimmed = sorted(rows, key=lambda row: row["total_volume"])[:keep]
    xs = [row["imbalance"] for row in trimmed]
    ys = [row["next_log_return"] for row in trimmed]
    return _pearson(xs, ys) > 0.0


def score_nonlockbox(rows: list[dict[str, float]], *, folds: int = 6) -> dict[str, Any]:
    if folds < 1:
        raise ValueError("folds must be positive")
    fold_size = len(rows) // folds
    fold_ics: list[float] = []
    for fold in range(folds):
        start = fold * fold_size
        end = len(rows) if fold == folds - 1 else (fold + 1) * fold_size
        part = rows[start:end]
        fold_ics.append(
            spearman_ic(
                [row["imbalance"] for row in part],
                [row["next_log_return"] for row in part],
            )
        )
    xs = [row["imbalance"] for row in rows]
    ys = [row["next_log_return"] for row in rows]
    return {
        "fold_count": folds,
        "fold_spearman_ic": fold_ics,
        "positive_fold_count": sum(1 for ic in fold_ics if ic > 0.0),
        "median_spearman_ic": median(fold_ics) if fold_ics else 0.0,
        "newey_west_t": _newey_west_t(xs, ys),
        "monotonic_bucket_check": _bucket_monotonic_check(rows),
        "trimmed_effect_positive": _trimmed_effect_positive(rows),
        "lockbox_touched": False,
    }


def evaluate_gate(score: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    fold_count = int(score.get("fold_count", 0))
    positive = int(score.get("positive_fold_count", 0))
    required_positive = 4 if fold_count == 6 else math.ceil((2.0 / 3.0) * fold_count)
    if fold_count < 6:
        failures.append("at least 6 chronological folds are required")
    if float(score.get("median_spearman_ic", 0.0)) <= 0.015:
        failures.append("median fold Spearman IC must be > 0.015")
    if positive < required_positive:
        failures.append("at least two-thirds of folds must be positive")
    if float(score.get("newey_west_t", 0.0)) < 2.0:
        failures.append("Newey-West t-statistic must be >= 2.0")
    if not bool(score.get("monotonic_bucket_check", False)):
        failures.append("highest imbalance bucket must beat lowest imbalance bucket")
    if not bool(score.get("trimmed_effect_positive", False)):
        failures.append("effect sign must remain positive after top 1% volume trim")
    if bool(score.get("lockbox_touched", True)):
        failures.append("lockbox must remain sealed")
    return {
        "status": "nonlockbox_pass" if not failures else "killed",
        "failures": failures,
        "score": score,
    }
```

- [ ] **Step 4: Run tests and verify Task 3 passes**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: `9 passed`.

- [ ] **Step 5: Commit Task 3**

```bash
rtk git add src/moonface/research/aggressor_trades.py tests/test_aggressor_trades.py
rtk git commit -m "feat(newdata): score aggressor trades rung0 gate"
```

## Task 4: End-To-End Pure Function And Report Rendering

**Files:**
- Modify: `src/moonface/research/aggressor_trades.py`
- Test: `tests/test_aggressor_trades.py`

- [ ] **Step 1: Add failing test for synthetic end-to-end result rendering**

Append to `tests/test_aggressor_trades.py`:

```python
from moonface.research.aggressor_trades import run_nonlockbox_rung0, render_report


class TestAggressorTradesReport(unittest.TestCase):
    def test_run_nonlockbox_rung0_renders_guardrailed_report(self):
        trades = []
        for i in range(240):
            side = "buy" if i % 2 == 0 else "sell"
            trades.append(
                TradePrint(
                    ts_ms=i * BUCKET_MS,
                    symbol="BTCUSDT",
                    side=side,
                    price=100.0 + i + (0.1 if side == "buy" else 0.0),
                    size=2.0 if side == "buy" else 1.0,
                )
            )

        result = run_nonlockbox_rung0(trades, cadence_ms=BUCKET_MS)
        report = render_report(result)

        self.assertIn(result["verdict"]["status"], {"nonlockbox_pass", "killed"})
        self.assertEqual(result["lockbox_touched"], False)
        self.assertIn("No strategy backtest was run.", report)
        self.assertIn("lockbox_touched: false", report)
        self.assertIn("This is not a trading result.", report)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: import failure for `run_nonlockbox_rung0` or `render_report`.

- [ ] **Step 3: Implement orchestration and report rendering**

Append to `src/moonface/research/aggressor_trades.py`:

```python
def run_nonlockbox_rung0(trades: list[TradePrint], *, cadence_ms: int = BUCKET_MS) -> dict[str, Any]:
    audit = audit_trades(trades, cadence_ms=cadence_ms)
    buckets = bucket_trades(trades)
    dev, lockbox = split_nonlockbox(buckets)
    if audit["status"] != "ready":
        score = {
            "fold_count": 0,
            "fold_spearman_ic": [],
            "positive_fold_count": 0,
            "median_spearman_ic": 0.0,
            "newey_west_t": 0.0,
            "monotonic_bucket_check": False,
            "trimmed_effect_positive": False,
            "lockbox_touched": False,
        }
        verdict = {"status": "killed", "failures": list(audit["failures"]), "score": score}
    else:
        score = score_nonlockbox(dev, folds=6)
        verdict = evaluate_gate(score)
    return {
        "status": verdict["status"],
        "audit": audit,
        "bucket_count": len(buckets),
        "nonlockbox_bucket_count": len(dev),
        "sealed_lockbox_bucket_count": len(lockbox),
        "lockbox_touched": False,
        "verdict": verdict,
    }


def render_report(result: dict[str, Any]) -> str:
    verdict = result["verdict"]
    lines = [
        "# Aggressor Trades Rung-0 Non-Lockbox Report",
        "",
        f"- status: {result['status']}",
        "- provider/data class: ExampleVendor aggressor_trades",
        "- universe: BTCUSDT perpetual",
        "- bucket: 5 minutes",
        "- horizon: next 5-minute bucket",
        "- lockbox_touched: false",
        "",
        "No strategy backtest was run.",
        "No sealed lockbox evaluation was run.",
        "This is not a trading result.",
        "",
        "## Gate Failures",
    ]
    failures = verdict.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## JSON Result",
            "",
            "```json",
            json.dumps(result, indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests and verify Task 4 passes**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py -q
```

Expected: `10 passed`.

- [ ] **Step 5: Commit Task 4**

```bash
rtk git add src/moonface/research/aggressor_trades.py tests/test_aggressor_trades.py
rtk git commit -m "feat(newdata): render aggressor trades rung0 report"
```

## Task 5: CLI With Synthetic-Test Coverage And One-Touch Artifact Refusal

**Files:**
- Create: `tools/aggressor_trades_rung0.py`
- Test: `tests/test_aggressor_trades_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_aggressor_trades_cli.py`:

```python
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.aggressor_trades_rung0 import cmd_nonlockbox


class TestAggressorTradesCli(unittest.TestCase):
    def write_synthetic_csv(self, path: Path) -> None:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ts_ms", "symbol", "side", "price", "size"])
            writer.writeheader()
            for i in range(220):
                side = "buy" if i % 2 == 0 else "sell"
                writer.writerow(
                    {
                        "ts_ms": i * 300_000,
                        "symbol": "BTCUSDT",
                        "side": side,
                        "price": 100.0 + i + (0.1 if side == "buy" else 0.0),
                        "size": 2.0 if side == "buy" else 1.0,
                    }
                )

    def test_cmd_nonlockbox_writes_artifacts_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "synthetic_trades.csv"
            out = root / "out"
            self.write_synthetic_csv(csv_path)

            result = cmd_nonlockbox(csv_path, out)

            self.assertEqual(result["lockbox_touched"], False)
            self.assertTrue((out / "audit.json").exists())
            self.assertTrue((out / "nonlockbox_results.json").exists())
            self.assertTrue((out / "report.md").exists())
            report = (out / "report.md").read_text()
            self.assertIn("No sealed lockbox evaluation was run.", report)
            with self.assertRaises(SystemExit):
                cmd_nonlockbox(csv_path, out)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
rtk pytest tests/test_aggressor_trades_cli.py -q
```

Expected: import failure for `tools.aggressor_trades_rung0`.

- [ ] **Step 3: Implement the CLI**

Create `tools/aggressor_trades_rung0.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.aggressor_trades import (
    BUCKET_MS,
    load_trade_csv,
    render_report,
    run_nonlockbox_rung0,
)


def cmd_nonlockbox(csv_path: Path, out_dir: Path) -> dict:
    result_path = out_dir / "nonlockbox_results.json"
    if result_path.exists():
        sys.exit(f"{result_path} already exists; Rung-0 non-lockbox assessment is one-touch")
    trades = load_trade_csv(csv_path)
    result = run_nonlockbox_rung0(trades, cadence_ms=BUCKET_MS)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "audit.json").write_text(json.dumps(result["audit"], indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    (out_dir / "report.md").write_text(render_report(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen aggressor-trades Rung-0 non-lockbox test.")
    parser.add_argument("--csv", required=True, help="Path to aggressor trade CSV with ts_ms,symbol,side,price,size")
    parser.add_argument("--out", required=True, help="Output directory for Rung-0 artifacts")
    parser.add_argument(
        "--open-lockbox",
        action="store_true",
        help="Always refused in this implementation plan; lockbox opening requires a separate approval.",
    )
    args = parser.parse_args()
    if args.open_lockbox:
        sys.exit("lockbox opening is not implemented; obtain explicit approval in a separate plan")
    result = cmd_nonlockbox(Path(args.csv), Path(args.out))
    print(f"[{result['status']}] lockbox_touched={str(result['lockbox_touched']).lower()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI tests and focused unit tests**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py tests/test_aggressor_trades_cli.py -q
```

Expected: `11 passed`.

- [ ] **Step 5: Commit Task 5**

```bash
rtk git add tools/aggressor_trades_rung0.py tests/test_aggressor_trades_cli.py
rtk git commit -m "feat(newdata): add aggressor trades rung0 cli"
```

## Task 6: Final Verification Without Real-Data Execution

**Files:**
- No source edits unless verification exposes a defect.

- [ ] **Step 1: Run focused synthetic test suite**

Run:

```bash
rtk pytest tests/test_aggressor_trades.py tests/test_aggressor_trades_cli.py tests/test_newdata.py tests/test_newdata_cli.py -q
```

Expected: all listed tests pass.

- [ ] **Step 2: Verify no real experiment artifacts were created**

Run:

```bash
rtk git status --short
```

Expected: only intended source/test/plan changes before final commit; no new `experiments/newdata/*/nonlockbox_results.json`, `audit.json`, or `report.md` from real provider data unless they came from explicitly synthetic temp tests outside the repo.

- [ ] **Step 3: Commit this implementation plan if it is still uncommitted**

```bash
rtk git add docs/research-log/plans/2026-06-17-aggressor-trades-rung0-implementation.md
rtk git commit -m "docs(newdata): plan aggressor trades rung0 implementation"
```

Expected: commit succeeds.

## Execution Gate

Stop after this plan is approved. Do not implement, run, or inspect the real provider data until the human explicitly chooses an execution approach and approves implementation.

Plan execution options:

1. Subagent-Driven: execute one task at a time with independent implementation and review between tasks.
2. Inline Execution: execute tasks in this session with checkpoints after each task.
