"""Aggressor-trades Rung-0 information test (v2, option A re-freeze).

Design frozen in experiments/newdata/AGGRESSOR_TRADES_RUNG0_PREREGISTRATION_V2.md.
The v1 feature (signed volume imbalance) was refuted as not-new before any run:
it is a strictly monotonic transform of the already-failed Binance
`sum_taker_long_short_vol_ratio` metric. v2 amends the FEATURE ONLY to a
genuinely trade-level quantity that no binned volume ratio can reproduce —
the excitation asymmetry of aggressive-trade *arrival timing*:

    feature = acf1(per-second buy print counts) - acf1(per-second sell counts)

over a trailing 6h window (a deterministic Hawkes-branching proxy; no MLE).
Input is per-second side counts plus last trade price — volumes are neither
required nor accepted. Buckets, horizon, folds, thresholds, and the sealed
lockbox are byte-identical to v1. This is an information test only, not a
backtest."""
from __future__ import annotations

import csv
import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

REQUIRED_FIELDS = ("ts_ms", "symbol", "buy_count", "sell_count", "last_price")
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
    "size",
    "volume",
    "buy_volume",
    "sell_volume",
    "imbalance",
}
SECOND_MS = 1_000
BUCKET_MS = 300_000
HORIZON_BUCKETS = 1
WINDOW_SECONDS = 21_600  # 6h trailing excitation window
LOCKBOX_FRACTION = 0.20
MIN_HISTORY_DAYS = 180
MIN_COVERAGE_RATIO = 0.95
MAX_DUPLICATE_TS_RATIO = 0.01


@dataclass(frozen=True, slots=True)
class SecondBar:
    ts_ms: int
    symbol: str
    buy_count: int
    sell_count: int
    last_price: float


def load_trade_csv(path: Path) -> list[SecondBar]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_FIELDS if name not in fieldnames]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        forbidden = sorted(set(fieldnames) & FORBIDDEN_FIELDS)
        if forbidden:
            raise ValueError(f"forbidden fields present: {', '.join(forbidden)}")

        i_ts = fieldnames.index("ts_ms")
        i_sym = fieldnames.index("symbol")
        i_buy = fieldnames.index("buy_count")
        i_sell = fieldnames.index("sell_count")
        i_price = fieldnames.index("last_price")
        rows: list[SecondBar] = []
        for rec in csv.reader(f):
            ts_ms = int(rec[i_ts])
            if ts_ms % SECOND_MS != 0:
                raise ValueError("ts_ms must be second-aligned")
            buy_count = int(rec[i_buy])
            sell_count = int(rec[i_sell])
            if buy_count < 0 or sell_count < 0:
                raise ValueError("counts must be non-negative")
            if buy_count + sell_count <= 0:
                raise ValueError("each row must contain at least one print")
            price = float(rec[i_price])
            if price <= 0.0:
                raise ValueError("last_price must be positive")
            rows.append(
                SecondBar(
                    ts_ms=ts_ms,
                    symbol=rec[i_sym].strip(),
                    buy_count=buy_count,
                    sell_count=sell_count,
                    last_price=price,
                )
            )
        return rows


def audit_trades(rows: list[SecondBar], *, cadence_ms: int) -> dict[str, Any]:
    failures: list[str] = []
    symbols = sorted({row.symbol for row in rows})
    timestamps = [row.ts_ms for row in rows]
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


def _acf1(m: int, first: float, last: float, s1: float, s2: float,
          sx: float) -> float:
    """Lag-1 autocorrelation of a window from its running sums: S1, S2, the
    adjacent-product sum Sx, and the boundary elements."""
    if m < 2:
        return 0.0
    mu = s1 / m
    den = s2 - m * mu * mu
    if den <= 0.0:
        return 0.0
    num = sx - mu * (2.0 * s1 - first - last) + (m - 1) * mu * mu
    return num / den


def bucket_trades(rows: list[SecondBar], *,
                  window_seconds: int = WINDOW_SECONDS) -> list[dict[str, float]]:
    """5-minute buckets carrying the frozen excitation-asymmetry feature.

    The feature at bucket t uses per-second print counts over the trailing
    `window_seconds` ending at the bucket's last second — information at or
    before the bucket close only. Buckets before the window is full are
    warmup and emit nothing. The outcome is the next emitted bucket's log
    price change, exactly as in v1."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: row.ts_ms)
    by_second = {row.ts_ms: (row.buy_count, row.sell_count, row.last_price)
                 for row in ordered}
    first_bucket = (ordered[0].ts_ms // BUCKET_MS) * BUCKET_MS
    last_bucket = (ordered[-1].ts_ms // BUCKET_MS) * BUCKET_MS
    # One flat pass with inlined sliding-window sums: the per-second loop runs
    # tens of millions of times on real data, so no per-second function calls.
    q: deque = deque()  # (buy, sell) pairs, window cap enforced below
    b1 = b2 = bx = 0.0
    s1 = s2 = sx = 0.0
    prev_b = prev_s = 0
    get = by_second.get
    emitted: list[dict[str, float]] = []
    for bucket_start in range(first_bucket, last_bucket + BUCKET_MS, BUCKET_MS):
        buy_count = 0
        sell_count = 0
        last_price: float | None = None
        for ts in range(bucket_start, bucket_start + BUCKET_MS, SECOND_MS):
            row = get(ts)
            if row is None:
                b = 0
                s = 0
            else:
                b, s, price = row
                last_price = price
                buy_count += b
                sell_count += s
            if q:
                bx += prev_b * b
                sx += prev_s * s
            b1 += b
            b2 += b * b
            s1 += s
            s2 += s * s
            q.append((b, s))
            prev_b = b
            prev_s = s
            if len(q) > window_seconds:
                ob, os_ = q.popleft()
                nb, ns = q[0]
                b1 -= ob
                b2 -= ob * ob
                bx -= ob * nb
                s1 -= os_
                s2 -= os_ * os_
                sx -= os_ * ns
        if last_price is None or buy_count + sell_count <= 0:
            continue
        m = len(q)
        if m < window_seconds:
            continue
        fb, fs = q[0]
        emitted.append(
            {
                "bucket_start_ms": bucket_start,
                "buy_count": float(buy_count),
                "sell_count": float(sell_count),
                "total_count": float(buy_count + sell_count),
                "excitation_asym": (_acf1(m, fb, prev_b, b1, b2, bx)
                                    - _acf1(m, fs, prev_s, s1, s2, sx)),
                "last_price": last_price,
            }
        )
    buckets: list[dict[str, float]] = []
    for idx, row in enumerate(emitted[:-HORIZON_BUCKETS]):
        next_row = emitted[idx + HORIZON_BUCKETS]
        buckets.append(
            {**row, "next_log_return": math.log(next_row["last_price"] / row["last_price"])}
        )
    return buckets


def split_nonlockbox(buckets: list[dict[str, float]]) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    fence = int(len(buckets) * (1.0 - LOCKBOX_FRACTION))
    return buckets[:fence], buckets[fence:]


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
    ordered = sorted(rows, key=lambda row: row["excitation_asym"])
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
    trimmed = sorted(rows, key=lambda row: row["total_count"])[:keep]
    xs = [row["excitation_asym"] for row in trimmed]
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
                [row["excitation_asym"] for row in part],
                [row["next_log_return"] for row in part],
            )
        )
    xs = [row["excitation_asym"] for row in rows]
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
        failures.append("highest excitation-asymmetry bucket must beat lowest excitation-asymmetry bucket")
    if not bool(score.get("trimmed_effect_positive", False)):
        failures.append("effect sign must remain positive after top 1% activity trim")
    if bool(score.get("lockbox_touched", True)):
        failures.append("lockbox must remain sealed")
    return {
        "status": "nonlockbox_pass" if not failures else "killed",
        "failures": failures,
        "score": score,
    }


def run_nonlockbox_rung0(rows: list[SecondBar], *, cadence_ms: int = BUCKET_MS) -> dict[str, Any]:
    audit = audit_trades(rows, cadence_ms=cadence_ms)
    buckets = bucket_trades(rows)
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
        "# Aggressor Trades Rung-0 Non-Lockbox Report (v2)",
        "",
        f"- status: {result['status']}",
        "- provider/data class: Binance Vision futures um daily aggTrades (per-second side counts)",
        "- universe: BTCUSDT perpetual",
        "- feature: excitation asymmetry (lag-1 autocorrelation of per-second buy prints"
        " minus sell prints, 6h trailing window)",
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
