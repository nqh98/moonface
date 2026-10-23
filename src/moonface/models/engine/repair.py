"""Read-only trend-score repair lane for the frozen engine."""
from __future__ import annotations

import random

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.core.stats import series_fingerprint, spearman
from moonface.kernel.bootstrap import resample_by_block_key
from moonface.models.engine.calibration import (
    BLOCK_BARS,
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    BUCKET_EDGES,
    BarRow,
    PANEL_FLOOR,
    HypoTrade,
    overlapping_panel,
    scoring_pass,
    simulate_entry,
)
from moonface.models.engine.confluence import BASE_THRESHOLD, BREADTH_MIN
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.honesty import cost_stress

TRAIN_END_TS_MS = 1688169600000
SEALED_START_TS_MS = 1748736000000
PURGE_MS = 168 * 3_600_000
FAMILY_ALPHA = 0.05
N_CANDIDATES = 3
CI_LO_Q = FAMILY_ALPHA / N_CANDIDATES / 2.0
CI_HI_Q = 1.0 - CI_LO_Q
OFFSET_GRID = (0, 5, 10, 15, 20)
CELL_FLOOR = 30
MONO_BUCKET_FLOOR = 30
CANDIDATES = ("c1_tier_merge", "c2_side_vol", "c3_isotonic")
REPAIR_LABEL = (
    "trend-score repair \u2014 pre-registered; read-only; "
    "no live constant changes; promotion is a human decision"
)


def segment_panel(panel: list[HypoTrade], train_end_ts_ms: int = TRAIN_END_TS_MS,
                  sealed_start_ts_ms: int = SEALED_START_TS_MS,
                  purge_ms: int = PURGE_MS,
                  ) -> tuple[dict[str, list[HypoTrade]], int]:
    segments: dict[str, list[HypoTrade]] = {
        "train": [],
        "validation": [],
        "sealed": [],
    }
    dropped = 0
    train_cutoff = train_end_ts_ms + purge_ms
    sealed_cutoff = sealed_start_ts_ms + purge_ms
    for trade in panel:
        if trade.exit_ts_ms < train_end_ts_ms:
            segments["train"].append(trade)
        elif trade.entry_ts_ms >= train_cutoff and trade.exit_ts_ms < sealed_start_ts_ms:
            segments["validation"].append(trade)
        elif trade.entry_ts_ms >= sealed_cutoff:
            segments["sealed"].append(trade)
        else:
            dropped += 1
    return segments, dropped


_C1_BOUNDS = ((0, 40), (40, 60), (60, 75), (75, 10**9))


def _pava_merge(items: list[list[float]]) -> list[list[float]]:
    blocks: list[list[float]] = []
    for mean, weight, size in items:
        blocks.append([mean, weight, size])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            m2, w2, s2 = blocks.pop()
            m1, w1, s1 = blocks.pop()
            total_weight = w1 + w2
            merged_mean = ((m1 * w1 + m2 * w2) / total_weight
                           if total_weight > 0 else 0.0)
            blocks.append([merged_mean, total_weight, s1 + s2])
    return blocks


def _pava_blocks(means: list[float], weights: list[float]) -> list[list[float]]:
    """Weighted pool-adjacent-violators; returns [mean, weight, size] blocks
    with weakly increasing means."""
    return _pava_merge([[mean, weight, 1] for mean, weight in zip(means, weights)])


def fit_tier_merge(train: list[HypoTrade]) -> tuple[int, ...]:
    """Kept interior edges after PAVA over the frozen buckets.

    Empty buckets merge left; a leading empty bucket merges right. Fewer than
    two populated buckets -> identity (the candidate degrades to a no-op).
    """
    groups: list[list[float]] = []
    leading_empty = 0
    for lo, hi in _C1_BOUNDS:
        rs = [trade.net_r for trade in train if lo <= trade.score < hi]
        if not rs:
            if groups:
                groups[-1][2] += 1
            else:
                leading_empty += 1
            continue
        size = 1 + leading_empty if not groups else 1
        groups.append([sum(rs) / len(rs), float(len(rs)), size])
        leading_empty = 0
    if len(groups) < 2:
        return BUCKET_EDGES
    blocks = _pava_merge(groups)
    kept: list[int] = []
    cum = 0
    for mean, weight, size in blocks[:-1]:
        del mean, weight
        cum += int(size)
        kept.append(BUCKET_EDGES[cum - 1])
    return tuple(kept)


def apply_tier_merge(score: int, kept_edges: tuple[int, ...]) -> int:
    return sum(1 for edge in kept_edges if score >= edge)


def c1_entry_threshold(kept_edges: tuple[int, ...]) -> int:
    """Lower edge of the merged bucket containing the frozen BASE_THRESHOLD."""
    return max((edge for edge in kept_edges if edge <= BASE_THRESHOLD), default=0)


_C2_CELLS = (("LONG", "normal"), ("LONG", "high"),
             ("SHORT", "normal"), ("SHORT", "high"))


def fit_side_vol_offsets(train: list[HypoTrade]) -> dict[tuple[str, str], int]:
    """Smallest grid offset where each cell's qualifying mean reaches the
    pooled qualifying mean. Underpowered pooled qualifiers -> no-op."""
    pooled_rs = [trade.net_r for trade in train if trade.score >= BASE_THRESHOLD]
    if len(pooled_rs) < CELL_FLOOR:
        return {cell: 0 for cell in _C2_CELLS}
    pooled_mean = sum(pooled_rs) / len(pooled_rs)
    offsets: dict[tuple[str, str], int] = {}
    for side, vol in _C2_CELLS:
        want = 1 if side == "LONG" else -1
        cell = [trade for trade in train
                if trade.direction == want and trade.vol_state == vol]
        chosen = OFFSET_GRID[-1]
        for off in OFFSET_GRID:
            rs = [trade.net_r for trade in cell
                  if trade.score >= BASE_THRESHOLD + off]
            if len(rs) < CELL_FLOOR:
                continue
            if sum(rs) / len(rs) >= pooled_mean:
                chosen = off
                break
        offsets[(side, vol)] = chosen
    return offsets


def apply_side_vol_offset(trade: HypoTrade,
                          offsets: dict[tuple[str, str], int]) -> float:
    side = "LONG" if trade.direction > 0 else "SHORT"
    return float(trade.score - offsets.get((side, trade.vol_state), 0))


def fit_isotonic(train: list[HypoTrade]) -> tuple[tuple[int, float], ...]:
    """Weighted isotonic regression of net R on the integer score."""
    by_score: dict[int, list[float]] = {}
    for trade in train:
        by_score.setdefault(trade.score, []).append(trade.net_r)
    scores = sorted(by_score)
    if not scores:
        return ()
    means = [sum(by_score[score]) / len(by_score[score]) for score in scores]
    weights = [float(len(by_score[score])) for score in scores]
    blocks = _pava_blocks(means, weights)
    fitted: list[tuple[int, float]] = []
    index = 0
    for mean, _, size in blocks:
        for _ in range(int(size)):
            fitted.append((scores[index], round(mean, 6)))
            index += 1
    return tuple(fitted)


def apply_isotonic(score: int, curve: tuple[tuple[int, float], ...]) -> float:
    if not curve:
        return 0.0
    value = curve[0][1]
    for s, v in curve:
        if s <= score:
            value = v
        else:
            break
    return value


def candidate_value(name: str, fitted, score: int, direction: int,
                    vol_state: str) -> float:
    if name == "c1_tier_merge":
        return float(apply_tier_merge(score, fitted))
    if name == "c2_side_vol":
        side = "LONG" if direction > 0 else "SHORT"
        return float(score - fitted.get((side, vol_state), 0))
    if name == "c3_isotonic":
        return apply_isotonic(score, fitted)
    raise ValueError(f"unknown candidate: {name}")


def score_trade(name: str, fitted, trade: HypoTrade) -> float:
    return candidate_value(name, fitted, trade.score, trade.direction,
                           trade.vol_state)


def block_ci_q(items: list, key_fn, stat_fn, lo_q: float, hi_q: float,
               block_bars: int = BLOCK_BARS, draws: int = BOOTSTRAP_DRAWS,
               seed: int = BOOTSTRAP_SEED) -> tuple[float, float] | None:
    blocks: dict[int, list] = {}
    for item in items:
        blocks.setdefault(key_fn(item) // block_bars, []).append(item)
    keys = sorted(blocks)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(draws):
        sample = resample_by_block_key(rng, blocks, keys)
        stat = stat_fn(sample)
        if stat is not None:
            stats.append(stat)
    if len(stats) < draws // 2:
        return None
    stats.sort()
    return (
        stats[int(lo_q * (len(stats) - 1))],
        stats[int(hi_q * (len(stats) - 1))],
    )


def train_quartile_edges(values: list[float]) -> tuple[float, float, float]:
    v = sorted(values)
    n = len(v)
    if n < 4:
        return (0.0, 0.0, 0.0)
    return (v[int(0.25 * (n - 1))], v[int(0.5 * (n - 1))],
            v[int(0.75 * (n - 1))])


def monotone_by_edges(trades: list[HypoTrade], name: str, fitted,
                      edges: tuple[float, float, float],
                      floor: int = MONO_BUCKET_FLOOR) -> dict:
    q1, q2, q3 = edges
    bounds = ((None, q1), (q1, q2), (q2, q3), (q3, None))
    buckets = []
    for lo, hi in bounds:
        rs = []
        for trade in trades:
            s = score_trade(name, fitted, trade)
            if (lo is None or s >= lo) and (hi is None or s < hi):
                rs.append(trade.net_r)
        buckets.append({
            "lo": lo,
            "hi": hi,
            "n": len(rs),
            "mean_net_r": round(sum(rs) / len(rs), 4) if rs else None,
        })
    means = [bucket["mean_net_r"] for bucket in buckets
             if bucket["n"] >= floor and bucket["mean_net_r"] is not None]
    return {"buckets": buckets,
            "monotone": all(b >= a for a, b in zip(means, means[1:]))}


def _delta_stat(name: str, fitted):
    def stat(sample: list[HypoTrade]) -> float | None:
        cand = spearman([score_trade(name, fitted, trade) for trade in sample],
                        [trade.net_r for trade in sample])
        base = spearman([float(trade.score) for trade in sample],
                        [trade.net_r for trade in sample])
        if cand is None or base is None:
            return None
        return cand - base
    return stat


def gate1_candidate(name: str, fitted, train: list[HypoTrade],
                    validation: list[HypoTrade]) -> dict:
    stat = _delta_stat(name, fitted)
    delta = stat(validation)
    ci = block_ci_q(validation, lambda trade: trade.entry_index, stat,
                    CI_LO_Q, CI_HI_Q)
    edges = train_quartile_edges(
        [score_trade(name, fitted, trade) for trade in train])
    mono = monotone_by_edges(validation, name, fitted, edges)
    passed = (len(validation) >= PANEL_FLOOR and delta is not None
              and ci is not None and ci[0] > 0 and mono["monotone"])
    return {"n": len(validation),
            "delta_rho": round(delta, 4) if delta is not None else None,
            "delta_ci": ([round(ci[0], 4), round(ci[1], 4)]
                         if ci is not None else None),
            "monotonicity": mono, "passed": passed}


def gate2_candidate(name: str, fitted, train: list[HypoTrade],
                    sealed: list[HypoTrade]) -> dict:
    stat = _delta_stat(name, fitted)
    delta = stat(sealed)
    edges = train_quartile_edges(
        [score_trade(name, fitted, trade) for trade in train])
    mono = monotone_by_edges(sealed, name, fitted, edges)
    passed = (len(sealed) >= PANEL_FLOOR and delta is not None
              and delta > 0 and mono["monotone"])
    return {"n": len(sealed),
            "delta_rho": round(delta, 4) if delta is not None else None,
            "monotonicity": mono, "passed": passed}


def qualify_fn_for(name: str, fitted):
    if name == "c1_tier_merge":
        threshold = c1_entry_threshold(fitted)
        return lambda row: row.trend.score >= threshold
    if name == "c2_side_vol":
        return lambda row: row.trend.score >= (
            BASE_THRESHOLD + fitted.get(("LONG", row.vol_state), 0))
    if name == "c3_isotonic":
        return lambda row: apply_isotonic(row.trend.score, fitted) > 0.0
    raise ValueError(f"unknown candidate: {name}")


def qualifier_stream(candles: list[Candle], cfg: EngineConfig,
                     rows: list[BarRow], qualify_fn,
                     ) -> list[tuple[HypoTrade, float]]:
    pairs: list[tuple[HypoTrade, float]] = []
    busy_until = -1
    for row in rows:
        if row.index <= busy_until:
            continue
        state = row.trend
        if state.direction != 1 or row.vol_state == "extreme":
            continue
        if state.policy != "ALLOW" or state.breadth < BREADTH_MIN:
            continue
        if not qualify_fn(row):
            continue
        trade = simulate_entry(candles, cfg, row, "trend")
        if trade is None:
            break
        tail = candles[max(0, row.index - cfg.atr_period):row.index + 1]
        close = candles[row.index].close
        atr_frac = atr(tail, cfg.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs


def replay_metrics(pairs: list[tuple[HypoTrade, float]],
                   cfg: EngineConfig) -> dict:
    ordered = sorted(pairs, key=lambda p: p[0].exit_ts_ms)
    rs = [trade.net_r for trade, _ in ordered]
    cum = 0.0
    peak = 0.0
    dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    stress = cost_stress([(trade.exit_ts_ms, trade.net_r, atr_frac,
                           cfg.base_fraction)
                          for trade, atr_frac in ordered])
    return {"n": len(rs), "net_r": round(sum(rs), 4),
            "max_dd_r": round(dd, 4), "cost_stress": stress}


def gate3_replay(candles: list[Candle], cfg: EngineConfig,
                 rows: list[BarRow], name: str, fitted) -> dict:
    base_pairs = qualifier_stream(
        candles, cfg, rows,
        lambda row: row.trend.score >= BASE_THRESHOLD)
    cand_pairs = qualifier_stream(candles, cfg, rows,
                                  qualify_fn_for(name, fitted))
    base = replay_metrics(base_pairs, cfg)
    cand = replay_metrics(cand_pairs, cfg)
    passed = (cand["n"] > 0
              and cand["net_r"] >= base["net_r"]
              and abs(cand["max_dd_r"]) <= abs(base["max_dd_r"])
              and cand["cost_stress"]["net_r_3x"] > 0)
    return {"baseline_v22": base, "candidate": cand, "passed": passed}


def fitted_payload(fitted: dict) -> dict:
    return {
        "c1_tier_merge": {
            "kept_edges": list(fitted["c1_tier_merge"]),
            "entry_threshold": c1_entry_threshold(fitted["c1_tier_merge"]),
        },
        "c2_side_vol": {
            f"{side}:{vol}": off
            for (side, vol), off in sorted(fitted["c2_side_vol"].items())
        },
        "c3_isotonic": [[s, v] for s, v in fitted["c3_isotonic"]],
    }


def fitted_from_payload(payload: dict) -> dict:
    offsets = {}
    for key, off in payload["c2_side_vol"].items():
        side, vol = key.split(":")
        offsets[(side, vol)] = off
    return {
        "c1_tier_merge": tuple(payload["c1_tier_merge"]["kept_edges"]),
        "c2_side_vol": offsets,
        "c3_isotonic": tuple((int(s), float(v))
                             for s, v in payload["c3_isotonic"]),
    }


def build_repair_report(cfg: EngineConfig, candles: list[Candle],
                        warmup: int,
                        train_end_ts_ms: int = TRAIN_END_TS_MS,
                        sealed_start_ts_ms: int = SEALED_START_TS_MS) -> dict:
    rows = scoring_pass(cfg, candles, warmup)
    panel, counts = overlapping_panel(candles, cfg, rows, "trend")
    segments, dropped = segment_panel(panel, train_end_ts_ms,
                                      sealed_start_ts_ms)
    fitted = {
        "c1_tier_merge": fit_tier_merge(segments["train"]),
        "c2_side_vol": fit_side_vol_offsets(segments["train"]),
        "c3_isotonic": fit_isotonic(segments["train"]),
    }
    gate1 = {
        name: gate1_candidate(name, fitted[name], segments["train"],
                              segments["validation"])
        for name in CANDIDATES
    }
    passers = [name for name in CANDIDATES if gate1[name]["passed"]]
    survivor = (max(passers, key=lambda name: gate1[name]["delta_rho"])
                if passers else None)
    gate2 = gate3 = None
    if survivor is None:
        verdict = "CLOSED_NEGATIVE_GATE1"
    else:
        gate2 = gate2_candidate(survivor, fitted[survivor],
                                segments["train"], segments["sealed"])
        if not gate2["passed"]:
            verdict = "CLOSED_NEGATIVE_GATE2"
        else:
            gate3 = gate3_replay(candles, cfg, rows, survivor,
                                 fitted[survivor])
            verdict = ("ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
                       if gate3["passed"] else "CLOSED_NEGATIVE_GATE3")
    return {
        "engine_hash": engine_hash(cfg),
        "label": REPAIR_LABEL,
        "data": {
            "candles": len(candles),
            "scored_bars": len(rows),
            "first_scored_ts_ms": rows[0].ts_ms if rows else None,
            "last_ts_ms": candles[-1].timestamp_ms if candles else None,
            "fingerprint_sha256": series_fingerprint(candles),
            "lookback_bars": cfg.lookback_bars,
            "warmup": warmup,
        },
        "frozen_analysis_constants": {
            "train_end_ts_ms": train_end_ts_ms,
            "sealed_start_ts_ms": sealed_start_ts_ms,
            "purge_ms": PURGE_MS,
            "family_alpha": FAMILY_ALPHA,
            "n_candidates": N_CANDIDATES,
            "ci_lo_q": CI_LO_Q,
            "ci_hi_q": CI_HI_Q,
            "offset_grid": list(OFFSET_GRID),
            "cell_floor": CELL_FLOOR,
            "mono_bucket_floor": MONO_BUCKET_FLOOR,
            "panel_floor": PANEL_FLOOR,
            "block_bars": BLOCK_BARS,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "panel_counts": counts,
        "segments": {"train": len(segments["train"]),
                     "validation": len(segments["validation"]),
                     "sealed": len(segments["sealed"]),
                     "dropped": dropped},
        "fitted": fitted_payload(fitted),
        "gate1": gate1,
        "survivor": survivor,
        "gate2": gate2,
        "gate3": gate3,
        "verdict": verdict,
    }
