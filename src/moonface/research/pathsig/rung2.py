# src/moonface/research/pathsig/rung2.py
"""Rung-2 distributional random forest harness.

Builds feature/label matrices from the shared Sample grid, selects forest
hyperparameters on an inner purged split, replays the forest on the existing
outer walk-forward folds with the unchanged decide() policy plus a quantile
ruin clamp, and scores the OOS stream under both risk frames. Verdict is
head-to-head against the rung-0 floor and the rung-1 result.
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung2-distributional-forest-design.md."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass

from moonface.research.pathsig.baseline import (
    ATR_PERIOD, DRAWDOWN_CAP_R, KELLY_SCALE, LOCKBOX_FRACTION, MAX_FRACTION,
    POOL_SYMBOLS, SLIPPAGE_BPS, TAKER_BPS)
from moonface.research.pathsig.data import build_btc_dataset
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.forest import DistForest, PathPrediction
from moonface.research.pathsig.policy import Decision, decide
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds

_ATR_IDX = FEATURE_NAMES.index("atr_frac")

# Frozen rung-2 hyperparameter grid and run constants.
STRUCTURE_GRID = [(d, m, mtry) for d in (3, 5) for m in (30, 60)
                  for mtry in (4, 8)]                       # 8 configs
EDGE_THRESHOLDS = (0.10, 0.20, 0.30)
N_TREES = 200
SEED = 12345
RUIN_Q05_R = -3.0
INNER_TRAIN_FRAC = 0.7
DSR_THRESHOLD = 0.95


def X_matrix(samples: list[Sample], positions: list[int]) -> np.ndarray:
    """(k, n_features) feature matrix for the given sample positions."""
    return np.array([samples[p].x for p in positions], dtype=float)


def labels_matrix(samples: list[Sample], positions: list[int]) -> np.ndarray:
    """(k, 3) label matrix: ret_r, mae_r, mfe_r for the given positions."""
    return np.array([[samples[p].label.ret_r, samples[p].label.mae_r,
                      samples[p].label.mfe_r] for p in positions], dtype=float)


def ruin_clamp(decision: Decision, pred: PathPrediction) -> Decision:
    """Zero a trade whose directional 5th-percentile return is worse than the
    frozen ruin floor. LONG adverse tail = q05; SHORT adverse tail = -q95."""
    if decision.action == "WAIT":
        return decision
    adverse = pred.q05 if decision.action == "LONG" else -pred.q95
    if adverse < RUIN_Q05_R:
        return Decision("WAIT", 0.0)
    return decision


def fit_config(samples: list[Sample], train_pos: list[int],
               structure: tuple[int, int, int]) -> DistForest:
    """Train a DistForest for one (max_depth, min_leaf, mtry) config on the
    given training positions. ret_r is the split target; the full label matrix
    feeds the leaf distributions."""
    max_depth, min_leaf, mtry = structure
    X = X_matrix(samples, train_pos)
    L = labels_matrix(samples, train_pos)
    return DistForest(n_trees=N_TREES, max_depth=max_depth, min_leaf=min_leaf,
                      mtry=mtry, seed=SEED).fit(X, L)


def replay_positions(samples: list[Sample], test_pos: list[int],
                      forest: DistForest, *, edge_threshold: float,
                      n_trials: int, trial_srs: list[float]) -> dict:
    """Decide on every test position from the forest's distribution (LONG-frame
    labels, so decide()'s LONG/SHORT map straight onto realized_r), apply the
    ruin clamp, and score the stream under both risk frames."""
    decisions, labels, atr_fracs, fundings = [], [], [], []
    for p in test_pos:
        pred = forest.predict(np.array(samples[p].x, dtype=float))
        dec = decide(pred.dist, edge_threshold, KELLY_SCALE, MAX_FRACTION)
        dec = ruin_clamp(dec, pred)
        decisions.append(dec)
        labels.append(samples[p].label)
        atr_fracs.append(samples[p].x[_ATR_IDX])
        fundings.append(0.0)
    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    if n_trades == 0:
        return {"status": "no_trades", "n_events": len(decisions), "n_trades": 0}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=TAKER_BPS, slippage_bps=SLIPPAGE_BPS,
                            n_trials=n_trials, trial_srs=trial_srs,
                            drawdown_cap_r=DRAWDOWN_CAP_R)
    return {"status": "ok", "n_events": len(decisions), "n_trades": n_trades,
            **res}


def inner_split(train_pos: list[int], embargo: int) -> tuple[list[int], list[int]]:
    """Carve a purged inner train/test from a contiguous outer train block.
    Inner test is the final (1 - INNER_TRAIN_FRAC) of the block; an embargo gap
    is removed from the end of inner train so horizon labels cannot leak."""
    n = len(train_pos)
    cut = int(n * INNER_TRAIN_FRAC)
    inner_train = train_pos[:max(0, cut - embargo)]
    inner_test = train_pos[cut:]
    return inner_train, inner_test


@dataclass(frozen=True)
class ConfigChoice:
    structure: tuple[int, int, int]
    edge_threshold: float
    trial_srs: list[float]


def select_config(samples: list[Sample], train_pos: list[int],
                  embargo: int) -> ConfigChoice:
    """Pick the (structure, edge_threshold) with the best inner-test Sharpe.
    Returns the choice plus every evaluated config's inner Sharpe (trial_srs for
    the deflation). Falls back to the first grid config if nothing trades."""
    inner_train, inner_test = inner_split(train_pos, embargo)
    trial_srs: list[float] = []
    best = None                                  # (sharpe, structure, threshold)
    for structure in STRUCTURE_GRID:
        forest = fit_config(samples, inner_train, structure)
        for et in EDGE_THRESHOLDS:
            res = replay_positions(samples, inner_test, forest,
                                   edge_threshold=et, n_trials=1, trial_srs=[])
            if res["status"] != "ok":
                continue
            sr = res["risk_adjusted"]["sharpe"]
            trial_srs.append(sr)
            if best is None or sr > best[0]:
                best = (sr, structure, et)
    if best is None:
        return ConfigChoice(structure=STRUCTURE_GRID[0],
                            edge_threshold=EDGE_THRESHOLDS[0], trial_srs=[])
    return ConfigChoice(structure=best[1], edge_threshold=best[2],
                        trial_srs=trial_srs)


def replay_forest(samples: list[Sample], folds: list[Fold], *, h: int,
                  n_trials: int) -> dict:
    """Nested walk-forward: per fold select a config on the train block, refit
    on the full train block, decide on every test bar, and score the pooled OOS
    stream. trial_srs is the union of all folds' inner Sharpes."""
    decisions: list[Decision] = []
    labels: list[PathLabel] = []
    atr_fracs: list[float] = []
    fundings: list[float] = []
    selected: list[dict] = []
    trial_srs: list[float] = []
    for fold in folds:
        choice = select_config(samples, fold.train_idx, embargo=h)
        trial_srs.extend(choice.trial_srs)
        forest = fit_config(samples, fold.train_idx, choice.structure)
        for p in fold.test_idx:
            pred = forest.predict(np.array(samples[p].x, dtype=float))
            dec = decide(pred.dist, choice.edge_threshold, KELLY_SCALE,
                         MAX_FRACTION)
            dec = ruin_clamp(dec, pred)
            decisions.append(dec)
            labels.append(samples[p].label)
            atr_fracs.append(samples[p].x[_ATR_IDX])
            fundings.append(0.0)
        selected.append({"structure": list(choice.structure),
                         "edge_threshold": choice.edge_threshold})

    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    if n_trades == 0:
        return {"status": "no_trades", "n_events": len(decisions),
                "n_trades": 0, "selected": selected}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=TAKER_BPS, slippage_bps=SLIPPAGE_BPS,
                            n_trials=n_trials, trial_srs=trial_srs,
                            drawdown_cap_r=DRAWDOWN_CAP_R)
    return {"status": "ok", "n_events": len(decisions), "n_trades": n_trades,
            "selected": selected, **res}


def _rung0_floor(rung0_doc: dict | None, h: int) -> dict | None:
    if not rung0_doc:
        return None
    ok = [r for r in rung0_doc.get("rows", [])
          if r.get("status") == "ok" and r.get("h") == h]
    if not ok:
        return None
    best = max(ok, key=lambda r: r["fixed_cap"]["total_r"])
    return {"best_total_r": best["fixed_cap"]["total_r"],
            "best_family": best["family"], "best_params": best["params"]}


def _rung1_result(rung1_doc: dict | None, h: int) -> dict | None:
    if not rung1_doc:
        return None
    for r in rung1_doc.get("rung1", []):
        if r.get("status") == "ok" and r.get("h") == h:
            return r
    return None


def rung2_verdict(result: dict, floor: dict | None,
                  rung1: dict | None) -> dict:
    """Success = beats the rung-0 floor AND the rung-1 result on fixed-cap
    total_r, AND clears the absolute DSR gate (dsr >= DSR_THRESHOLD). There is
    no relative-DSR check against rung-1 — only the absolute gate above."""
    if result.get("status") != "ok":
        return {"h": result.get("h"), "beats_rung0": False, "beats_rung1": False,
                "clears_gate": False, "note": "forest produced no trades"}
    total_r = result["fixed_cap"]["total_r"]
    dsr = result["risk_adjusted"]["dsr"]
    beats0 = floor is None or total_r > floor["best_total_r"]
    beats1 = (rung1 is None or rung1.get("status") != "ok"
              or total_r > rung1["fixed_cap"]["total_r"])
    clears = dsr >= DSR_THRESHOLD
    if clears and beats0 and beats1:
        note = "forest beats rung-1 and rung-0 AND clears the DSR gate"
    elif beats0 and beats1:
        note = "path model helps but is not deflation-significant"
    else:
        note = "forest does not beat the rungs below it"
    return {"h": result.get("h"), "beats_rung0": beats0, "beats_rung1": beats1,
            "clears_gate": clears, "note": note}


def run_rung2_to_doc(readers: dict, *, n_folds: int, horizons: list[int],
                     pool_symbols: list[str] = POOL_SYMBOLS,
                     deploy: str = "BTCUSDT", rung0_doc: dict | None = None,
                     rung1_doc: dict | None = None) -> dict:
    """Full rung-2 results document from injectable readers (offline testable).
    One result + verdict per horizon. n_trials = |structure| x |thresholds| x
    |horizons| (deflation budget), passed identically to every horizon."""
    n_trials = len(STRUCTURE_GRID) * len(EDGE_THRESHOLDS) * len(horizons)
    rung2, verdict = [], []
    for h in horizons:
        _, samples = build_btc_dataset(readers, h=h, atr_period=ATR_PERIOD,
                                       pool_symbols=pool_symbols, deploy=deploy)
        folds = walk_forward_folds(len(samples), n_folds=n_folds, embargo=h,
                                   lockbox_fraction=LOCKBOX_FRACTION)
        res = replay_forest(samples, folds, h=h, n_trials=n_trials)
        res["h"] = h
        rung2.append(res)
        verdict.append(rung2_verdict(res, _rung0_floor(rung0_doc, h),
                                     _rung1_result(rung1_doc, h)))
    return {
        "config": {
            "deploy": deploy, "horizons": horizons, "n_folds": n_folds,
            "lockbox_fraction": LOCKBOX_FRACTION, "atr_period": ATR_PERIOD,
            "n_trees": N_TREES, "structure_grid": [list(s) for s in STRUCTURE_GRID],
            "edge_thresholds": list(EDGE_THRESHOLDS), "seed": SEED,
            "ruin_q05_r": RUIN_Q05_R, "kelly_scale": KELLY_SCALE,
            "max_fraction": MAX_FRACTION, "taker_bps": TAKER_BPS,
            "slippage_bps": SLIPPAGE_BPS, "drawdown_cap_r": DRAWDOWN_CAP_R,
            "dsr_threshold": DSR_THRESHOLD, "n_trials": n_trials,
            "pool_symbols": pool_symbols,
        },
        "rung2": rung2,
        "rung0_floor": {h: _rung0_floor(rung0_doc, h) for h in horizons},
        "verdict": verdict,
    }


def open_lockbox(samples: list[Sample], *, h: int, n_trials: int) -> dict:
    """One-touch sealed-tail evaluation. Select a config via inner CV on all
    usable (non-lockbox) data, refit on all usable data, and score the sealed
    final lockbox_fraction tail exactly once. Run only after OOS success."""
    n = len(samples)
    usable = int(n * (1.0 - LOCKBOX_FRACTION))
    train_pos = list(range(usable))
    tail_pos = list(range(usable, n))
    choice = select_config(samples, train_pos, embargo=h)
    forest = fit_config(samples, train_pos, choice.structure)
    res = replay_positions(samples, tail_pos, forest,
                           edge_threshold=choice.edge_threshold,
                           n_trials=n_trials, trial_srs=choice.trial_srs)
    res["h"] = h
    res["selected"] = {"structure": list(choice.structure),
                        "edge_threshold": choice.edge_threshold}
    return res
