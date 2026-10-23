"""Read-only scoring audit foundation for the frozen v2 engine."""
from __future__ import annotations

import math
import random

from moonface.core.models import Candle
from moonface.core.stats import series_fingerprint, spearman
from moonface.kernel.bootstrap import resample_by_block_key
from moonface.models.engine.calibration import (
    BLOCK_BARS,
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    PANEL_FLOOR,
    _REVERT_MODULES,
    _TREND_MODULES,
    BarRow,
    HypoTrade,
    overlapping_panel,
    scoring_pass,
)
from moonface.models.engine.config import EngineConfig, engine_hash

BOOK_MODULES: dict[str, tuple[str, ...]] = {
    "trend": _TREND_MODULES,
    "mean_revert": _REVERT_MODULES,
}
_SPLITS = ("pooled", "LONG", "SHORT")
TRAIN_FRACTION = 0.6
PURGE_BARS = BLOCK_BARS
NNLS_SWEEPS = 200
LOGIT_ITERS = 300
LOGIT_LR = 0.1

AUDIT_LABEL = (
    "scoring audit — read-only, no edge claim, "
    "no constant recommendation"
)


def block_ci(items: list, key_fn, stat_fn, block_bars: int = BLOCK_BARS,
             draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED,
             ) -> tuple[float, float] | None:
    """95% CI of stat_fn(resample) via a moving-block bootstrap."""
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
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return (lo, hi)


def _split_trades(panel: list[HypoTrade], split: str) -> list[HypoTrade]:
    if split == "pooled":
        return list(panel)
    if split == "LONG":
        want = 1
    elif split == "SHORT":
        want = -1
    else:
        raise ValueError(f"unknown split: {split}")
    return [trade for trade in panel if trade.direction == want]


def _rho_stat(trades: list[HypoTrade]) -> float | None:
    return spearman([float(trade.score) for trade in trades],
                    [trade.net_r for trade in trades])


def _ci_out(ci: tuple[float, float] | None) -> list[float] | None:
    return [round(ci[0], 4), round(ci[1], 4)] if ci is not None else None


def baseline_ordering(panel: list[HypoTrade]) -> dict:
    """Spearman(score, net_r) with a block-bootstrap CI per split."""
    out: dict[str, dict] = {}
    for split in _SPLITS:
        trades = _split_trades(panel, split)
        rho = _rho_stat(trades)
        ci = block_ci(trades, lambda trade: trade.entry_index, _rho_stat)
        out[split] = {
            "n": len(trades),
            "spearman_rho": round(rho, 4) if rho is not None else None,
            "rho_ci_95": _ci_out(ci),
            "status": "UNDERPOWERED" if len(trades) < PANEL_FLOOR else "ok",
        }
    return out


def loo_book_score(row: BarRow, book: str, drop: str) -> tuple[int, int]:
    """(direction, score) of the book sum without one module."""
    score = sum(points for module, points in row.module_points.items()
                if module in BOOK_MODULES[book] and module != drop)
    direction = 1 if score > 0 else (-1 if score < 0 else 0)
    return direction, abs(score)


def loo_analysis(panel: list[HypoTrade], rows_by_index: dict[int, BarRow],
                 book: str) -> dict:
    """Marginal contribution per module and split."""

    def _delta(sample: list[tuple[HypoTrade, int]]) -> float | None:
        base = spearman([float(t.score) for t, _ in sample],
                        [t.net_r for t, _ in sample])
        loo = spearman([float(s) for _, s in sample],
                       [t.net_r for t, _ in sample])
        if base is None or loo is None:
            return None
        return loo - base

    out: dict[str, dict] = {}
    for drop in BOOK_MODULES[book]:
        kept_all: list[tuple[HypoTrade, int]] = []
        changed = 0
        for trade in panel:
            direction, score = loo_book_score(
                rows_by_index[trade.entry_index], book, drop)
            if direction != trade.direction:
                changed += 1
                continue
            kept_all.append((trade, score))
        splits: dict[str, dict] = {}
        for split in _SPLITS:
            if split == "pooled":
                kept = kept_all
            else:
                want = 1 if split == "LONG" else -1
                kept = [(trade, score) for trade, score in kept_all
                        if trade.direction == want]
            delta = _delta(kept)
            ci = block_ci(kept, lambda item: item[0].entry_index, _delta)
            if len(kept) < PANEL_FLOOR or delta is None or ci is None:
                klass = "UNDERPOWERED"
            elif ci[1] < 0:
                klass = "CONTRIBUTES"
            elif ci[0] > 0:
                klass = "HARMFUL"
            else:
                klass = "DEAD"
            splits[split] = {
                "n_kept": len(kept),
                "delta_rho": round(delta, 4) if delta is not None else None,
                "delta_ci_95": _ci_out(ci),
                "class": klass,
            }
        out[drop] = {"n_direction_changed": changed, "splits": splits}
    return out


def conditional_ordering(panel: list[HypoTrade],
                         rows_by_index: dict[int, BarRow],
                         book: str) -> dict:
    """Spearman(direction-aligned module points, net R) per module and split."""
    out: dict[str, dict] = {}
    for module in BOOK_MODULES[book]:
        splits: dict[str, dict] = {}
        for split in _SPLITS:
            trades = _split_trades(panel, split)
            pairs = [
                (trade, float(trade.direction
                              * rows_by_index[trade.entry_index]
                              .module_points[module]))
                for trade in trades
            ]

            def _stat(sample: list[tuple[HypoTrade, float]]) -> float | None:
                return spearman([score for _, score in sample],
                                [trade.net_r for trade, _ in sample])

            rho = _stat(pairs)
            ci = block_ci(pairs, lambda item: item[0].entry_index, _stat)
            splits[split] = {
                "n": len(pairs),
                "spearman_rho": round(rho, 4) if rho is not None else None,
                "rho_ci_95": _ci_out(ci),
                "status": "UNDERPOWERED" if len(pairs) < PANEL_FLOOR else "ok",
            }
        out[module] = splits
    return out


def chrono_split(panel: list[HypoTrade], rows: list[BarRow],
                 ) -> tuple[list[HypoTrade], list[HypoTrade], int, int]:
    """Leakage-safe chronological split for fitted upper-bound analysis."""
    boundary = rows[int(TRAIN_FRACTION * len(rows))].index
    train = [trade for trade in panel if trade.exit_index < boundary]
    test = [
        trade for trade in panel
        if trade.entry_index >= boundary + PURGE_BARS
    ]
    dropped = len(panel) - len(train) - len(test)
    return train, test, boundary, dropped


def _features(trades: list[HypoTrade], rows_by_index: dict[int, BarRow],
              book: str) -> list[list[float]]:
    modules = BOOK_MODULES[book]
    return [
        [
            float(trade.direction
                  * rows_by_index[trade.entry_index].module_points[module])
            for module in modules
        ]
        for trade in trades
    ]


def _standardize_fit(X: list[list[float]]) -> tuple[list[float], list[float]]:
    n = len(X)
    k = len(X[0])
    means = [sum(row[col] for row in X) / n for col in range(k)]
    sds: list[float] = []
    for col in range(k):
        var = sum((row[col] - means[col]) ** 2 for row in X) / n
        sds.append(math.sqrt(var) if var > 0.0 else 1.0)
    return means, sds


def _standardize_apply(X: list[list[float]], means: list[float],
                       sds: list[float]) -> list[list[float]]:
    return [
        [(row[col] - means[col]) / sds[col] for col in range(len(means))]
        for row in X
    ]


def fit_nnls(X: list[list[float]], y: list[float],
             sweeps: int = NNLS_SWEEPS) -> list[float]:
    """Nonnegative least squares via deterministic coordinate descent."""
    n = len(X)
    k = len(X[0])
    gram = [
        [sum(X[row][a] * X[row][b] for row in range(n)) for b in range(k)]
        for a in range(k)
    ]
    c = [sum(X[row][a] * y[row] for row in range(n)) for a in range(k)]
    w = [0.0] * k
    for _ in range(sweeps):
        for a in range(k):
            if gram[a][a] == 0.0:
                w[a] = 0.0
                continue
            resid = c[a] - sum(
                gram[a][b] * w[b] for b in range(k) if b != a)
            w[a] = max(0.0, resid / gram[a][a])
    return w


def fit_logistic(X: list[list[float]], y01: list[float],
                 iters: int = LOGIT_ITERS, lr: float = LOGIT_LR,
                 ) -> tuple[list[float], float]:
    """Projected-gradient logistic regression with nonnegative weights."""
    n = len(X)
    k = len(X[0])
    w = [0.0] * k
    bias = 0.0
    for _ in range(iters):
        gw = [0.0] * k
        gb = 0.0
        for i in range(n):
            z = bias + sum(w[col] * X[i][col] for col in range(k))
            z = max(-35.0, min(35.0, z))
            err = 1.0 / (1.0 + math.exp(-z)) - y01[i]
            gb += err
            for col in range(k):
                gw[col] += err * X[i][col]
        bias -= lr * gb / n
        for col in range(k):
            w[col] = max(0.0, w[col] - lr * gw[col] / n)
    return w, bias


def normalize_weights(w: list[float]) -> tuple[list[float], bool]:
    """Sum-normalize nonnegative fitter weights to 100."""
    total = sum(w)
    if total <= 0.0:
        return [0.0] * len(w), True
    return [100.0 * value / total for value in w], False


def _oos_ordering(pairs: list[tuple[HypoTrade, float]]) -> dict:
    out: dict[str, dict] = {}
    for split in _SPLITS:
        if split == "pooled":
            sub = pairs
        else:
            want = 1 if split == "LONG" else -1
            sub = [(trade, score) for trade, score in pairs
                   if trade.direction == want]

        def _stat(sample: list[tuple[HypoTrade, float]]) -> float | None:
            return spearman([score for _, score in sample],
                            [trade.net_r for trade, _ in sample])

        rho = _stat(sub)
        ci = block_ci(sub, lambda item: item[0].entry_index, _stat)
        out[split] = {
            "n": len(sub),
            "spearman_rho": round(rho, 4) if rho is not None else None,
            "rho_ci_95": _ci_out(ci),
            "status": "UNDERPOWERED" if len(sub) < PANEL_FLOOR else "ok",
        }
    return out


def fitted_upper_bound(panel: list[HypoTrade], rows: list[BarRow],
                       rows_by_index: dict[int, BarRow], book: str) -> dict:
    """Could any nonnegative reweighting order outcomes out of sample?"""
    train, test, boundary, dropped = chrono_split(panel, rows)
    result: dict = {
        "train_n": len(train),
        "test_n": len(test),
        "boundary_index": boundary,
        "dropped": dropped,
    }
    if len(train) < PANEL_FLOOR or len(test) < PANEL_FLOOR:
        result["status"] = "UNDERPOWERED"
        return result

    modules = BOOK_MODULES[book]
    train_raw = _features(train, rows_by_index, book)
    test_raw = _features(test, rows_by_index, book)
    means, sds = _standardize_fit(train_raw)
    x_train = _standardize_apply(train_raw, means, sds)
    x_test = _standardize_apply(test_raw, means, sds)
    fits = {
        "nnls_net_r": fit_nnls(x_train, [trade.net_r for trade in train]),
        "logistic_win": fit_logistic(
            x_train, [1.0 if trade.net_r > 0.0 else 0.0
                      for trade in train])[0],
    }

    result["fitters"] = {}
    for name, raw in fits.items():
        weights, degenerate = normalize_weights(raw)
        scores = [
            sum(weights[col] * x_test[i][col] for col in range(len(modules)))
            for i in range(len(test))
        ]
        result["fitters"][name] = {
            "weights": {
                module: round(weights[col], 2)
                for col, module in enumerate(modules)
            },
            "degenerate": degenerate,
            "oos": _oos_ordering(list(zip(test, scores))),
        }

    result["current"] = {
        "oos": _oos_ordering([(trade, float(trade.score)) for trade in test]),
    }
    result["status"] = "ok"
    return result


def _clean_positive(oos_block: dict | None) -> bool:
    if not oos_block:
        return False
    pooled = oos_block.get("oos", {}).get("pooled", {})
    ci = pooled.get("rho_ci_95")
    return bool(ci) and ci[0] > 0 and pooled.get("status") == "ok"


def book_verdict(fit_result: dict) -> str:
    """Spec §7 precedence (amended: 'any weighting' = fitters union current)."""
    if fit_result.get("status") != "ok":
        return "UNDERPOWERED"
    current_ok = _clean_positive(fit_result.get("current"))
    fitter_ok = any(_clean_positive(fit)
                    for fit in fit_result.get("fitters", {}).values())
    if not current_ok and not fitter_ok:
        return "NO_SIGNAL_IN_ANY_WEIGHTING"
    if current_ok:
        return "CURRENT_WEIGHTS_ADEQUATE"
    return "WEIGHTS_MISCALIBRATED"


def build_audit_report(cfg: EngineConfig, candles: list[Candle], warmup: int,
                       deriv_by_index: dict | None = None, stage: int = 1,
                       deriv_meta: dict | None = None) -> dict:
    """Full audit report (spec §5, §7) with frozen panel construction."""
    rows = scoring_pass(cfg, candles, warmup, deriv_by_index=deriv_by_index)
    rows_by_index = {row.index: row for row in rows}
    books: dict[str, dict] = {}
    for book in ("trend", "mean_revert"):
        panel, counts = overlapping_panel(candles, cfg, rows, book)
        fit = fitted_upper_bound(panel, rows, rows_by_index, book)
        books[book] = {
            "panel_counts": counts,
            "baseline": baseline_ordering(panel),
            "loo": loo_analysis(panel, rows_by_index, book),
            "conditional": conditional_ordering(panel, rows_by_index, book),
            "fitted_upper_bound": fit,
            "verdict": book_verdict(fit),
        }
    return {
        "engine_hash": engine_hash(cfg),
        "label": AUDIT_LABEL,
        "stage": stage,
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
            "block_bars": BLOCK_BARS,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "panel_floor": PANEL_FLOOR,
            "train_fraction": TRAIN_FRACTION,
            "purge_bars": PURGE_BARS,
            "nnls_sweeps": NNLS_SWEEPS,
            "logit_iters": LOGIT_ITERS,
            "logit_lr": LOGIT_LR,
        },
        "deriv": deriv_meta,
        "books": books,
    }
