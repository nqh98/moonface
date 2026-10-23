"""Conditional event study: forward risk distribution of external entry
events, bucketed by regime label at event time.

Descriptive only. Nothing here emits a pass/fail; the bucket report and the
null calibration exist so a human can see whether a conditional difference
is even distinguishable from label shuffling."""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.core.risk import horizon_r, risk_unit
from moonface.kernel.bootstrap import iid_resample_randrange
from moonface.research.microscope.regimes import UNLABELED

HORIZONS = (6, 12, 42)
PRIMARY_HORIZON = 12
EXCURSION_BARS = 42
K_ATR = 2.0
ATR_PERIOD = 14
TARGET_R = 1.0
POWER_FLOOR = 30
N_BOOT = 2000
N_SHUFFLES = 200


@dataclass(frozen=True)
class Event:
    ts_ms: int
    symbol: str
    direction: int      # +1 long, -1 short


def excursions(candles, i: int, direction: int, risk: float,
               bars: int = EXCURSION_BARS,
               target_r: float = TARGET_R
               ) -> tuple[float, float, bool | None]:
    """(MFE, MAE, stop_first) over the excursion window, in R units.
    A bar touching both stop and target counts as stop (conservative).
    stop_first is None when neither level is hit inside the window."""
    entry = candles[i].close
    stop = entry - risk * direction
    target = entry + risk * direction * target_r
    mfe = 0.0
    mae = 0.0
    stop_first: bool | None = None
    last = min(i + bars, len(candles) - 1)
    for j in range(i + 1, last + 1):
        hi = candles[j].high
        lo = candles[j].low
        if direction > 0:
            fav, adv = (hi - entry) / risk, (entry - lo) / risk
            hit_stop, hit_target = lo <= stop, hi >= target
        else:
            fav, adv = (entry - lo) / risk, (hi - entry) / risk
            hit_stop, hit_target = hi >= stop, lo <= target
        mfe = max(mfe, fav)
        mae = max(mae, adv)
        if stop_first is None:
            if hit_stop:
                stop_first = True
            elif hit_target:
                stop_first = False
    return round(mfe, 4), round(mae, 4), stop_first


def forward_vol(candles, i: int,
                bars: int = PRIMARY_HORIZON) -> float | None:
    """Population stdev of the next `bars` 1-bar returns; None if the
    series ends before the window completes."""
    rets = []
    last = min(i + bars, len(candles) - 1)
    for j in range(i + 1, last + 1):
        prev = candles[j - 1].close
        if prev > 0:
            rets.append(candles[j].close / prev - 1.0)
    if len(rets) < bars:
        return None
    m = sum(rets) / len(rets)
    return round((sum((r - m) ** 2 for r in rets) / len(rets)) ** 0.5, 6)


def event_outcomes(pool: dict[str, DataBundle],
                   labels: dict[str, list[str]],
                   timestamps: list[int],
                   events: list[Event]) -> list[dict]:
    """One outcome row per usable event. Events with an unknown symbol, a
    timestamp that is not a pool bar, or an undefined risk unit are dropped
    (callers report the drop count by comparing lengths)."""
    ts_index = {ts: i for i, ts in enumerate(timestamps)}
    candle_index = {sym: {c.timestamp_ms: i for i, c in enumerate(b.candles)}
                    for sym, b in pool.items()}
    out: list[dict] = []
    for ev in events:
        b = pool.get(ev.symbol)
        if b is None:
            continue
        i = candle_index[ev.symbol].get(ev.ts_ms)
        t = ts_index.get(ev.ts_ms)
        if i is None or t is None:
            continue
        risk = risk_unit(b.candles, i, K_ATR, ATR_PERIOD)
        if risk is None:
            continue
        side = "LONG" if ev.direction > 0 else "SHORT"
        row: dict = {"symbol": ev.symbol, "ts_ms": ev.ts_ms,
                     "direction": ev.direction,
                     "label": labels[ev.symbol][t]}
        for h in HORIZONS:
            row[f"fwd_r_{h}"] = horizon_r(i, side, b.candles, K_ATR,
                                          ATR_PERIOD, h)
        mfe, mae, stop_first = excursions(b.candles, i, ev.direction, risk)
        row["mfe_r"] = mfe
        row["mae_r"] = mae
        row["stop_first"] = stop_first
        row["fwd_vol"] = forward_vol(b.candles, i)
        out.append(row)
    return out


def _iqr(values: list[float]) -> float:
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q3 - q1


def bootstrap_ci(values: list[float], seed: int,
                 n_boot: int = N_BOOT) -> tuple[float, float]:
    """Seeded percentile bootstrap (2.5/97.5) of the mean."""
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        means.append(sum(iid_resample_randrange(rng, values)) / len(values))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[min(int(0.975 * n_boot), n_boot - 1)]
    return round(lo, 4), round(hi, 4)


def bucket_report(outcomes: list[dict], seed: int = 0) -> list[dict]:
    """Per-regime-bucket descriptive statistics. Buckets below POWER_FLOOR
    say nothing beyond their size — no direction, no CI. UNLABELED rows
    are excluded (spec §3.3); the caller reports their count."""
    by_label: dict[str, list[dict]] = {}
    for row in outcomes:
        if row["label"] == UNLABELED:
            continue
        by_label.setdefault(row["label"], []).append(row)
    report: list[dict] = []
    for lbl in sorted(by_label):
        rows = by_label[lbl]
        entry: dict = {"label": lbl, "n": len(rows)}
        if len(rows) < POWER_FLOOR:
            entry["verdict"] = "INSUFFICIENT_DATA"
            report.append(entry)
            continue
        entry["verdict"] = "DESCRIPTIVE"
        for h in HORIZONS:
            vals = [r[f"fwd_r_{h}"] for r in rows
                    if r[f"fwd_r_{h}"] is not None]
            if len(vals) < POWER_FLOOR:
                continue
            entry[f"fwd_r_{h}_mean"] = round(sum(vals) / len(vals), 4)
            entry[f"fwd_r_{h}_ci"] = bootstrap_ci(vals, seed=seed + h)
        mfes = [r["mfe_r"] for r in rows]
        maes = [r["mae_r"] for r in rows]
        entry["mfe_r_median"] = round(statistics.median(mfes), 4)
        entry["mfe_r_iqr"] = round(_iqr(mfes), 4)
        entry["mae_r_median"] = round(statistics.median(maes), 4)
        entry["mae_r_iqr"] = round(_iqr(maes), 4)
        resolved = [r["stop_first"] for r in rows
                    if r["stop_first"] is not None]
        entry["n_resolved"] = len(resolved)
        entry["p_stop_first"] = (round(sum(resolved) / len(resolved), 4)
                                 if resolved else None)
        vols = [r["fwd_vol"] for r in rows if r["fwd_vol"] is not None]
        entry["fwd_vol_mean"] = (round(sum(vols) / len(vols), 6)
                                 if vols else None)
        report.append(entry)
    return report


def effect_size(outcomes: list[dict]) -> float:
    """Spread (max - min) of mean primary-horizon R across buckets with
    n >= POWER_FLOOR, UNLABELED excluded. 0.0 when fewer than two such
    buckets exist — a spread needs two ends."""
    by_label: dict[str, list[float]] = {}
    for row in outcomes:
        v = row[f"fwd_r_{PRIMARY_HORIZON}"]
        if v is not None and row["label"] != UNLABELED:
            by_label.setdefault(row["label"], []).append(v)
    means = [sum(v) / len(v) for v in by_label.values()
             if len(v) >= POWER_FLOOR]
    if len(means) < 2:
        return 0.0
    return max(means) - min(means)


def null_calibration(outcomes: list[dict], seed: int = 0,
                     n_shuffles: int = N_SHUFFLES) -> dict:
    """Re-run the effect with regime labels time-shuffled. A real
    conditional effect must beat the shuffled distribution; one that
    survives shuffling is a selection artifact (the vol-compression
    gotcha, made permanent: a valid effect must FAIL on null)."""
    real = effect_size(outcomes)
    rng = random.Random(seed)
    labels = [r["label"] for r in outcomes]
    null_effects: list[float] = []
    beaten = 0
    for _ in range(n_shuffles):
        shuffled = labels[:]
        rng.shuffle(shuffled)
        rows = [{**r, "label": lbl} for r, lbl in zip(outcomes, shuffled)]
        e = effect_size(rows)
        null_effects.append(e)
        if real > e:
            beaten += 1
    null_effects.sort()
    p95 = null_effects[int(0.95 * n_shuffles)] if n_shuffles else 0.0
    verdict = ("EXCEEDS_NULL" if real > p95 and real > 0.0
               else "INDISTINGUISHABLE_FROM_NULL")
    return {"real_effect": round(real, 4), "null_p95": round(p95, 4),
            "pct_beaten": round(beaten / n_shuffles, 4), "verdict": verdict}
