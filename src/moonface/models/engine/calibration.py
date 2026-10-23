"""Read-only score-calibration diagnostic for the frozen v2 engine.

The pass mirrors the frozen call sequence used by evaluate_engine and exposes a
bar-wise diagnostic row for downstream calibration tasks. This module is
read-only: it does not gate, mutate, or recommend changes to the frozen engine.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.stats import _ranks, series_fingerprint, spearman
from moonface.kernel.bootstrap import resample_by_block_key
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import (BASE_THRESHOLD, BREADTH_MIN,
                                               CT_SURCHARGE, EXCLUDED_MODULES,
                                               GATE, decide)
from moonface.models.engine.deriv import DerivSnapshot
from moonface.models.engine.macro import classify_macro
from moonface.models.engine.modules import revert_book, trend_book
from moonface.models.engine.regime import classify_regime
from moonface.models.engine.position import PositionState, manage_position, open_position

BLOCK_BARS = 168
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 20260704
IC_HORIZON_BARS = 24
NW_LAG = 24
BUCKET_EDGES = (40, 60, 75)
PANEL_FLOOR = 200
TRIGGER_BUCKET_FLOOR = 30

_TREND_MODULES = (
    "m1_macro",
    "m2_breakout",
    "m2_ma_align",
    "m3_roc",
    "m4_pullback",
    "m5_funding",
)
_REVERT_MODULES = (
    "m1_sweep",
    "m2_reclaim",
    "m3_divergence",
    "m4_fund_ct",
    "m5_oi_flush",
    "m6_stretch",
)
_BOOK_LABEL = {"trend": "TREND", "mean_revert": "MEAN_REVERT"}
_DIR_LABEL = {1: "LONG", -1: "SHORT"}

DIAGNOSTIC_LABEL = (
    "calibration diagnostic — read-only, no edge claim, "
    "no constant recommendation"
)


@dataclass(frozen=True)
class BookState:
    direction: int
    score: int
    breadth: int
    policy: str | None


@dataclass(frozen=True)
class BarRow:
    index: int
    ts_ms: int
    macro_effective: str
    vol_state: str
    regime_trend: int
    trend: BookState
    revert: BookState
    module_points: dict[str, int]
    sweep_wick: float | None
    decision_action: str
    decision_direction: int
    decision_score: int


def _book_state(book_scores, archetype: str, macro_effective: str) -> BookState:
    signed = sum(m.direction * m.points for m in book_scores)
    direction = 1 if signed > 0 else (-1 if signed < 0 else 0)
    score = abs(signed)
    breadth = sum(1 for m in book_scores
                  if m.direction == direction and m.points > 0)
    policy = None
    if direction != 0:
        policy = GATE[(macro_effective, _BOOK_LABEL[archetype],
                       _DIR_LABEL[direction])]
    return BookState(direction, score, breadth, policy)


def scoring_pass(cfg: EngineConfig, candles: list[Candle], warmup: int,
                 deriv_by_index: dict[int, DerivSnapshot] | None = None
                 ) -> list[BarRow]:
    """Mirror the frozen evaluate_engine scoring sequence over a rolling window."""
    window = cfg.lookback_bars
    rows: list[BarRow] = []
    for j in range(warmup, len(candles)):
        lo = max(0, j + 1 - window)
        sub = candles[lo:j + 1]
        views = trend_book.build_views(sub)
        regime = classify_regime(views.h4, cfg)
        macro = classify_macro(views.w1, regime.vol_state, cfg)
        deriv = None if deriv_by_index is None else deriv_by_index.get(j)
        trend_scores = trend_book.score(views, macro, deriv, cfg)
        revert_scores = revert_book.score(views, macro, deriv, cfg)
        decision = decide(trend_scores, revert_scores, macro, cfg)
        macro_eff = macro.effective()
        t_state = _book_state(
            [m for m in trend_scores if m.module not in EXCLUDED_MODULES],
            "trend", macro_eff)
        r_state = _book_state(revert_scores, "mean_revert", macro_eff)
        module_points = {m.module: m.direction * m.points
                         for m in list(trend_scores) + list(revert_scores)}
        sweep_wick = None
        if r_state.direction != 0:
            sw = revert_book.sweep_state(views.h1)
            if sw is not None and sw.direction == r_state.direction:
                sweep_wick = sw.wick_extreme
        rows.append(BarRow(
            index=j, ts_ms=candles[j].timestamp_ms,
            macro_effective=macro_eff, vol_state=regime.vol_state,
            regime_trend=regime.trend, trend=t_state, revert=r_state,
            module_points=module_points, sweep_wick=sweep_wick,
            decision_action=decision.action,
            decision_direction=decision.direction,
            decision_score=decision.score))
    return rows


@dataclass(frozen=True)
class HypoTrade:
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    book: str
    direction: int
    score: int
    breadth: int
    policy: str | None
    macro_effective: str
    vol_state: str
    net_r: float
    bars_held: int
    exit_reason: str


def _row_state(row: BarRow, book: str) -> BookState:
    if book == "trend":
        return row.trend
    if book == "mean_revert":
        return row.revert
    raise ValueError(f"unknown book: {book}")


def simulate_entry(candles: list[Candle], cfg: EngineConfig, row: BarRow,
                   book: str,
                   rows_by_index: dict[int, BarRow] | None = None,
                   ) -> HypoTrade | None:
    """Open at row.index close with the frozen entry/exit discipline; manage
    bar-by-bar to EXIT. Returns None when the data ends first (caller counts
    incompletes). rows_by_index enables the opposite-SETUP reversal exit, used
    only by reversal_sensitivity — the primary panels pass None (spec §4b).

    ATR note: foundation.risk.atr averages the last `period` true ranges, so
    the (atr_period+1)-bar tail slice reproduces the full-history value
    exactly. manage_position reads only candles[-1], so each management step
    passes a single-bar list."""
    state = _row_state(row, book)
    profile = "WT" if book == "trend" else "CT"
    j = row.index
    tail = candles[max(0, j - cfg.atr_period):j + 1]
    sweep_wick = row.sweep_wick if profile == "CT" else None
    step = open_position(tail, cfg, state.direction, state.score / 100.0,
                         cfg.base_fraction, profile, sweep_wick)
    pos = PositionState(direction=state.direction,
                        entry_price=step.entry_price, stop=step.stop,
                        extreme=step.extreme, atr_at_entry=step.atr_at_entry,
                        fraction=cfg.base_fraction, bars_held=0,
                        profile=profile, target=step.target)
    for k in range(j + 1, len(candles)):
        signal_dir = 0
        if rows_by_index is not None:
            r_k = rows_by_index.get(k)
            if r_k is not None and r_k.decision_action == "SETUP":
                signal_dir = r_k.decision_direction
        step = manage_position([candles[k]], cfg, pos, signal_dir,
                               state.score / 100.0)
        if step.action == "EXIT":
            return HypoTrade(
                entry_index=j, exit_index=k, entry_ts_ms=row.ts_ms,
                exit_ts_ms=candles[k].timestamp_ms, book=book,
                direction=state.direction, score=state.score,
                breadth=state.breadth, policy=state.policy,
                macro_effective=row.macro_effective, vol_state=row.vol_state,
                net_r=step.realized_r, bars_held=step.bars_held,
                exit_reason=step.reason)
        pos = PositionState(direction=pos.direction,
                            entry_price=pos.entry_price, stop=step.stop,
                            extreme=step.extreme,
                            atr_at_entry=pos.atr_at_entry,
                            fraction=pos.fraction, bars_held=step.bars_held,
                            profile=profile, target=step.target)
    return None


def overlapping_panel(candles: list[Candle], cfg: EngineConfig,
                      rows: list[BarRow], book: str,
                      ) -> tuple[list[HypoTrade], dict]:
    """Primary calibration sample: EVERY directional, non-extreme-vol bar is a
    hypothetical entry (threshold-free). Overlap is handled at inference time
    by the moving-block bootstrap. Extreme-vol bars are excluded because the
    frozen decide() stands flat there at any score."""
    trades: list[HypoTrade] = []
    incomplete = 0
    skipped_extreme = 0
    for row in rows:
        state = _row_state(row, book)
        if state.direction == 0:
            continue
        if row.vol_state == "extreme":
            skipped_extreme += 1
            continue
        t = simulate_entry(candles, cfg, row, book)
        if t is None:
            incomplete += 1
        else:
            trades.append(t)
    return trades, {"events": len(trades), "incomplete": incomplete,
                    "skipped_extreme_vol": skipped_extreme}


def nonoverlapping_stream(candles: list[Candle], cfg: EngineConfig,
                          rows: list[BarRow], book: str) -> list[HypoTrade]:
    """Robustness sample: one position at a time per book (live sequencing
    shape, threshold-free)."""
    trades: list[HypoTrade] = []
    busy_until = -1
    for row in rows:
        if row.index <= busy_until:
            continue
        state = _row_state(row, book)
        if state.direction == 0 or row.vol_state == "extreme":
            continue
        t = simulate_entry(candles, cfg, row, book)
        if t is None:
            break
        trades.append(t)
        busy_until = t.exit_index
    return trades


def reversal_sensitivity(candles: list[Candle], cfg: EngineConfig,
                         rows: list[BarRow], book: str) -> dict:
    """Bound the no-reversal assumption (spec §4b): the actual-trigger subset
    (frozen threshold + breadth + non-REJECT gate) simulated with and without
    the opposite-SETUP reversal exit."""
    rows_by_index = {r.index: r for r in rows}
    triggered: list[BarRow] = []
    for row in rows:
        state = _row_state(row, book)
        if state.direction == 0 or row.vol_state == "extreme":
            continue
        if state.policy in (None, "REJECT"):
            continue
        threshold = BASE_THRESHOLD + (CT_SURCHARGE
                                      if state.policy == "ALLOW_CT" else 0)
        if state.breadth >= BREADTH_MIN and state.score >= threshold:
            triggered.append(row)

    def _net(with_reversal: bool) -> tuple[int, float]:
        total, count = 0.0, 0
        for row in triggered:
            t = simulate_entry(candles, cfg, row, book,
                               rows_by_index if with_reversal else None)
            if t is not None:
                total += t.net_r
                count += 1
        return count, round(total, 4)

    n_no, r_no = _net(False)
    n_rev, r_rev = _net(True)
    return {"triggered_events": len(triggered),
            "no_reversal": {"n": n_no, "net_r": r_no},
            "with_reversal": {"n": n_rev, "net_r": r_rev},
            "net_r_gap": round(r_rev - r_no, 4)}


def block_bootstrap_rho_ci(trades: list[HypoTrade],
                           block_bars: int = BLOCK_BARS,
                           draws: int = BOOTSTRAP_DRAWS,
                           seed: int = BOOTSTRAP_SEED,
                           ) -> tuple[float, float] | None:
    """95% CI for spearman(score, net_r) via a moving-block bootstrap keyed on
    entry-bar blocks (overlap-honest inference for the overlapping panel)."""
    blocks: dict[int, list[HypoTrade]] = {}
    for t in trades:
        blocks.setdefault(t.entry_index // block_bars, []).append(t)
    keys = sorted(blocks)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(draws):
        sample = resample_by_block_key(rng, blocks, keys)
        rho = spearman([float(t.score) for t in sample],
                       [t.net_r for t in sample])
        if rho is not None:
            stats.append(rho)
    if len(stats) < draws // 2:
        return None
    stats.sort()
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return (lo, hi)


def bucket_stats(trades: list[HypoTrade]) -> list[dict]:
    e0, e1, e2 = BUCKET_EDGES
    bounds = [(0, e0), (e0, e1), (e1, e2), (e2, 10 ** 9)]
    out = []
    for lo, hi in bounds:
        rs = [t.net_r for t in trades if lo <= t.score < hi]
        label = f">={lo}" if hi >= 10 ** 9 else f"[{lo},{hi})"
        out.append({"bucket": label, "n": len(rs),
                    "mean_net_r": (round(sum(rs) / len(rs), 4)
                                   if rs else None)})
    return out


def buckets_weakly_increasing(buckets: list[dict]) -> bool:
    means = [b["mean_net_r"] for b in buckets if b["mean_net_r"] is not None]
    return all(b >= a for a, b in zip(means, means[1:]))


def nw_tstat_of_mean(z: list[float], lag: int = NW_LAG) -> float | None:
    """t-stat of mean(z) with Newey-West (Bartlett) long-run variance."""
    n = len(z)
    if n < lag + 2:
        return None
    mean = sum(z) / n
    d = [v - mean for v in z]
    var = sum(x * x for x in d) / n
    cov_sum = 0.0
    for el in range(1, lag + 1):
        w = 1.0 - el / (lag + 1.0)
        cov = sum(d[i] * d[i - el] for i in range(el, n)) / n
        cov_sum += 2.0 * w * cov
    lrv = var + cov_sum
    if lrv <= 0:
        return None
    se = math.sqrt(lrv / n)
    return mean / se if se > 0 else None


def _standardized_ranks(values: list[float]) -> list[float]:
    r = _ranks(values)
    n = len(r)
    m = sum(r) / n
    var = sum((a - m) ** 2 for a in r) / n
    if var == 0:
        return [0.0] * n
    sd = math.sqrt(var)
    return [(a - m) / sd for a in r]


def module_ic_table(rows: list[BarRow], candles: list[Candle],
                    horizon: int = IC_HORIZON_BARS) -> list[dict]:
    """SECONDARY diagnostic (spec §4d): per-module rank-IC vs forward log
    return, NW t. Suspect-ranking only — never verdict-bearing; fixed-horizon
    drift has repeatedly failed brackets in this program."""
    usable = [r for r in rows if r.index + horizon < len(candles)]
    out: list[dict] = []
    if not usable:
        return out
    fwd = [math.log(candles[r.index + horizon].close
                    / candles[r.index].close) for r in usable]
    for name in _TREND_MODULES + _REVERT_MODULES:
        xs = [float(r.module_points.get(name, 0)) for r in usable]
        rho = spearman(xs, fwd)
        if rho is None:
            out.append({"module": name, "rank_ic": None, "nw_t": None,
                        "n": len(usable)})
            continue
        rx = _standardized_ranks(xs)
        ry = _standardized_ranks(fwd)
        z = [a * b for a, b in zip(rx, ry)]
        t = nw_tstat_of_mean(z)
        out.append({"module": name, "rank_ic": round(rho, 4),
                    "nw_t": round(t, 3) if t is not None else None,
                    "n": len(usable)})
    return out


def classify_book(trades: list[HypoTrade], first_ts: int,
                  last_ts: int) -> dict:
    """Pre-registered book classification (spec §4c). Power floor applies
    REGARDLESS of whether the statistics would pass or fail."""
    n = len(trades)
    trig_n = sum(1 for t in trades if t.score >= BASE_THRESHOLD)
    rho = spearman([float(t.score) for t in trades],
                   [t.net_r for t in trades])
    ci = block_bootstrap_rho_ci(trades)
    buckets = bucket_stats(trades)
    mono = buckets_weakly_increasing(buckets)
    mid = first_ts + (last_ts - first_ts) // 2
    h1 = [t for t in trades if t.entry_ts_ms < mid]
    h2 = [t for t in trades if t.entry_ts_ms >= mid]
    rho_h1 = spearman([float(t.score) for t in h1], [t.net_r for t in h1])
    rho_h2 = spearman([float(t.score) for t in h2], [t.net_r for t in h2])
    stable = (rho_h1 is not None and rho_h2 is not None
              and (rho_h1 > 0) == (rho_h2 > 0))
    underpowered = n < PANEL_FLOOR or trig_n < TRIGGER_BUCKET_FLOOR
    passes = (rho is not None and rho > 0
              and ci is not None and ci[0] > 0
              and mono and stable)
    status = ("underpowered" if underpowered
              else ("pass" if passes else "fail"))
    return {
        "events": n,
        "events_score_ge_60": trig_n,
        "spearman_rho": round(rho, 4) if rho is not None else None,
        "rho_ci_95": ([round(ci[0], 4), round(ci[1], 4)]
                      if ci is not None else None),
        "buckets": buckets,
        "buckets_weakly_increasing": mono,
        "rho_first_half": round(rho_h1, 4) if rho_h1 is not None else None,
        "rho_second_half": round(rho_h2, 4) if rho_h2 is not None else None,
        "stability_sign_agrees": stable,
        "status": status,
    }


def overall_verdict(trend_status: str, revert_status: str) -> str:
    statuses = (trend_status, revert_status)
    if all(s == "pass" for s in statuses):
        return "CALIBRATED"
    if any(s == "pass" for s in statuses):
        return "PARTIALLY_CALIBRATED"
    if any(s == "fail" for s in statuses):
        return "UNCALIBRATED"
    return "UNDERPOWERED"


def split_summary(trades: list[HypoTrade], key_fn) -> dict[str, dict]:
    groups: dict[str, list[float]] = {}
    for t in trades:
        groups.setdefault(key_fn(t), []).append(t.net_r)
    return {k: {"n": len(v), "mean_net_r": round(sum(v) / len(v), 4)}
            for k, v in sorted(groups.items())}


ASSUMPTIONS = (
    "deriv=None throughout: verdict covers the PRICE-STRUCTURE core only "
    "(trend book caps at 85/100 without m5_funding; revert book lacks "
    "m4_fund_ct and m5_oi_flush)",
    "hypothetical trades below the frozen threshold are counterfactual: the "
    "live engine never takes them; they exist to measure score ordering",
    "primary panels run the frozen exit discipline WITHOUT the opposite-SETUP "
    "reversal exit (undefined sub-threshold); reversal_sensitivity bounds "
    "the distortion on the actual-trigger subset",
    "extreme-vol bars are excluded from entries: the frozen decide() stands "
    "flat there at any score (excluded counts reported)",
    "net_r is per-unit R from the frozen cost model; sizing fractions do not "
    "affect it",
    "halves split at the midpoint timestamp of the scored span "
    "(approximates the spec's calendar halves)",
)


def build_report(cfg: EngineConfig, candles: list[Candle],
                 warmup: int) -> dict:
    rows = scoring_pass(cfg, candles, warmup)
    first_ts = rows[0].ts_ms if rows else None
    last_ts = candles[-1].timestamp_ms if candles else None
    books: dict[str, dict] = {}
    for book in ("trend", "mean_revert"):
        panel, counts = overlapping_panel(candles, cfg, rows, book)
        stream = nonoverlapping_stream(candles, cfg, rows, book)
        stream_rho = spearman([float(t.score) for t in stream],
                              [t.net_r for t in stream])
        books[book] = {
            "panel_counts": counts,
            "calibration": classify_book(panel, first_ts or 0, last_ts or 0),
            "splits": {
                "policy": split_summary(panel, lambda t: t.policy or "NONE"),
                "direction": split_summary(
                    panel,
                    lambda t: "LONG" if t.direction > 0 else "SHORT"),
                "vol_state": split_summary(panel, lambda t: t.vol_state),
            },
            "nonoverlapping": {
                "events": len(stream),
                "spearman_rho": (round(stream_rho, 4)
                                 if stream_rho is not None else None),
            },
            "reversal_sensitivity": reversal_sensitivity(
                candles, cfg, rows, book),
        }
    verdict = overall_verdict(
        books["trend"]["calibration"]["status"],
        books["mean_revert"]["calibration"]["status"])
    return {
        "engine_hash": engine_hash(cfg),
        "label": DIAGNOSTIC_LABEL,
        "data": {
            "candles": len(candles),
            "scored_bars": len(rows),
            "first_scored_ts_ms": first_ts,
            "last_ts_ms": last_ts,
            "fingerprint_sha256": series_fingerprint(candles),
            "lookback_bars": cfg.lookback_bars,
            "warmup": warmup,
        },
        "frozen_analysis_constants": {
            "block_bars": BLOCK_BARS, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "ic_horizon_bars": IC_HORIZON_BARS, "nw_lag": NW_LAG,
            "bucket_edges": list(BUCKET_EDGES),
            "panel_floor": PANEL_FLOOR,
            "trigger_bucket_floor": TRIGGER_BUCKET_FLOOR,
        },
        "assumptions": list(ASSUMPTIONS),
        "books": books,
        "module_ic_secondary": module_ic_table(rows, candles),
        "verdict": verdict,
    }
