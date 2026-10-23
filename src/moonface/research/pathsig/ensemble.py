"""Rung-1 regime-weighted ensemble of the existing signal families.

Each bar is classified into one of 4 fit-free regime buckets (trend/range x
low/high vol) from the frozen features. Per fold, per (signal, regime), the
rung-0 fit_distribution gives a signal-frame Distribution and a non-negative
edge weight; at each test bar the firing signals' distributions are converted to
the market (LONG) frame and weight-averaged into one ensemble Distribution, fed
to the shared decide() -> evaluate_strategy(). The control rung 2 must beat.
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung1-ensemble-design.md."""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.research.entries import UnknownEntryFamily, generate_entries
from moonface.research.pathsig.baseline import (
    ATR_PERIOD, DRAWDOWN_CAP_R, EDGE_THRESHOLD, KELLY_SCALE, LOCKBOX_FRACTION,
    MAX_FRACTION, MIN_FIT_EVENTS, POOL_SYMBOLS, SIGNALS, SLIPPAGE_BPS, TAKER_BPS,
    _METRICS_FIELD, fit_distribution,
)
from moonface.research.pathsig.data import build_btc_dataset
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.policy import Decision, Distribution, decide
from moonface.research.pathsig.walkforward import walk_forward_folds

REGIME_WINDOW = 180
N_REGIMES = 4

_RVOL_IDX = FEATURE_NAMES.index("rvol_24")
_MA_IDX = FEATURE_NAMES.index("ma100_dist")


def _trailing_rank(values: list[float], i: int, window: int) -> float:
    """Percentile rank of values[i] among the up-to-`window` samples strictly
    before i (fraction strictly below). 0.0 when no prior sample exists."""
    lo = max(0, i - window)
    prior = values[lo:i]
    if not prior:
        return 0.0
    return sum(1 for x in prior if x < values[i]) / len(prior)


def assign_regimes(samples, window: int = REGIME_WINDOW) -> list[int]:
    """Per-bar regime id in {0,1,2,3} = trend_bit*2 + vol_bit, from trailing
    ranks of rvol_24 (vol axis) and abs(ma100_dist) (trend axis)."""
    rvol = [s.x[_RVOL_IDX] for s in samples]
    mdist = [abs(s.x[_MA_IDX]) for s in samples]
    out: list[int] = []
    for i in range(len(samples)):
        vol_bit = 1 if _trailing_rank(rvol, i, window) >= 0.5 else 0
        trend_bit = 1 if _trailing_rank(mdist, i, window) >= 0.5 else 0
        out.append(trend_bit * 2 + vol_bit)
    return out


def cell_weight(dist: Distribution | None) -> float:
    """Non-negative train edge (exp_ret_r / |exp_mae_r|) of a fitted cell."""
    if dist is None:
        return 0.0
    denom = abs(dist.exp_mae_r)
    if denom <= 0.0:
        return 0.0
    return max(0.0, dist.exp_ret_r / denom)


def _to_market(dist: Distribution, side: str) -> Distribution:
    """Reframe a signal-frame distribution into the market (LONG) frame. For a
    SHORT fire the market drift is negated and the excursions swap+negate."""
    if side == "LONG":
        return dist
    return Distribution(p_up=1.0 - dist.p_up, exp_ret_r=-dist.exp_ret_r,
                        exp_mae_r=-dist.exp_mfe_r, exp_mfe_r=-dist.exp_mae_r)


def ensemble_distribution(contribs: list[tuple[Distribution, float]]
                          ) -> Distribution | None:
    """Weight-normalized average of market-frame contributions. None when there
    is no positive total weight."""
    tw = sum(w for _, w in contribs)
    if tw <= 0.0:
        return None
    return Distribution(
        p_up=sum(m.p_up * w for m, w in contribs) / tw,
        exp_ret_r=sum(m.exp_ret_r * w for m, w in contribs) / tw,
        exp_mae_r=sum(m.exp_mae_r * w for m, w in contribs) / tw,
        exp_mfe_r=sum(m.exp_mfe_r * w for m, w in contribs) / tw)

_ATR_IDX = FEATURE_NAMES.index("atr_frac")


def replay_ensemble(samples, folds, regimes: list[int],
                    fires: dict[int, dict[int, str]], *, edge_threshold: float,
                    kelly_scale: float, max_fraction: float, taker_bps: float,
                    slippage_bps: float, min_events: int,
                    trial_srs: list[float], drawdown_cap_r: float) -> dict:
    """Fold loop over per-signal fire-maps. Per fold: fit per-(signal, regime)
    cells on train; per fired test bar blend the cells into one decision. Scores
    the concatenated stream under both risk frames."""
    decisions, labels, atr_fracs, fundings = [], [], [], []
    for fold in folds:
        cells: dict[int, dict[int, tuple[Distribution, float]]] = {}
        for sid, fire in fires.items():
            per_regime: dict[int, tuple[Distribution, float]] = {}
            for r in range(N_REGIMES):
                positions = [p for p in fold.train_idx
                             if regimes[p] == r and samples[p].index in fire]
                dist = fit_distribution(samples, fire, positions, min_events)
                w = cell_weight(dist)
                if w > 0.0:
                    per_regime[r] = (dist, w)
            cells[sid] = per_regime

        for p in fold.test_idx:
            r = regimes[p]
            fired = [(sid, fire[samples[p].index]) for sid, fire in fires.items()
                     if samples[p].index in fire]
            if not fired:
                continue
            contribs = []
            for sid, side in fired:
                cell = cells[sid].get(r)
                if cell is None:
                    continue
                dist, w = cell
                contribs.append((_to_market(dist, side), w))
            ens = ensemble_distribution(contribs)
            dec = (Decision("WAIT", 0.0) if ens is None
                   else decide(ens, edge_threshold, kelly_scale, max_fraction))
            decisions.append(dec)
            labels.append(samples[p].label)
            atr_fracs.append(samples[p].x[_ATR_IDX])
            fundings.append(0.0)

    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    if n_trades == 0:
        return {"status": "no_trades", "n_events": len(decisions),
                "n_trades": 0}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=taker_bps, slippage_bps=slippage_bps,
                            n_trials=max(1, len(trial_srs)), trial_srs=trial_srs,
                            drawdown_cap_r=drawdown_cap_r)
    return {"status": "ok", "n_events": len(decisions), "n_trades": n_trades,
            **res}

DSR_THRESHOLD = 0.95


def _trial_srs_from_rung0(rung0_doc: dict | None, h: int) -> list[float]:
    if not rung0_doc:
        return []
    return [r["risk_adjusted"]["sharpe"] for r in rung0_doc.get("rows", [])
            if r.get("status") == "ok" and r.get("h") == h]


def _rung0_floor(rung0_doc: dict | None, h: int) -> dict | None:
    if not rung0_doc:
        return None
    ok = [r for r in rung0_doc.get("rows", [])
          if r.get("status") == "ok" and r.get("h") == h]
    if not ok:
        return None
    best = max(ok, key=lambda r: r["fixed_cap"]["total_r"])
    return {"best_total_r": best["fixed_cap"]["total_r"],
            "best_dsr": max(r["risk_adjusted"]["dsr"] for r in ok),
            "best_family": best["family"], "best_params": best["params"]}


def _verdict(result: dict, floor: dict | None) -> dict:
    if result.get("status") != "ok":
        return {"h": result.get("h"), "beats_rung0": False, "clears_gate": False,
                "note": "ensemble produced no trades"}
    total_r = result["fixed_cap"]["total_r"]
    dsr = result["risk_adjusted"]["dsr"]
    beats = floor is None or total_r > floor["best_total_r"]
    clears = dsr >= DSR_THRESHOLD
    if clears and beats:
        note = "ensemble beats rung-0 floor AND clears DSR gate"
    elif beats:
        note = "ensembling helps but is not deflation-significant"
    else:
        note = "ensemble does not beat the rung-0 floor"
    return {"h": result.get("h"), "beats_rung0": beats, "clears_gate": clears,
            "note": note}


def run_ensemble_to_doc(readers: dict, *, n_folds: int, horizons: list[int],
                        pool_symbols: list[str] = POOL_SYMBOLS,
                        deploy: str = "BTCUSDT",
                        rung0_doc: dict | None = None) -> dict:
    """Build the full rung-1 results document from injectable readers (offline
    testable). One result per horizon, each with a head-to-head verdict against
    the rung-0 floor."""
    rung1, verdict = [], []
    for h in horizons:
        base, samples = build_btc_dataset(readers, h=h, atr_period=ATR_PERIOD,
                                          pool_symbols=pool_symbols, deploy=deploy)
        folds = walk_forward_folds(len(samples), n_folds=n_folds, embargo=h,
                                   lockbox_fraction=LOCKBOX_FRACTION)
        regimes = assign_regimes(samples)
        fires: dict[int, dict[int, str]] = {}
        for sid, spec in enumerate(SIGNALS):
            family, params = spec["family"], spec["params"]
            field = _METRICS_FIELD.get(family, "sum_open_interest")
            bundle = DataBundle(candles=base.candles, funding=base.funding,
                                feature=readers["metrics"](deploy, field),
                                bookdepth=base.bookdepth)
            try:
                events = generate_entries(family, params, bundle)
            except (ValueError, UnknownEntryFamily):
                continue
            fires[sid] = {i: side for i, side in events}

        trial_srs = _trial_srs_from_rung0(rung0_doc, h)
        res = replay_ensemble(samples, folds, regimes, fires,
                              edge_threshold=EDGE_THRESHOLD,
                              kelly_scale=KELLY_SCALE, max_fraction=MAX_FRACTION,
                              taker_bps=TAKER_BPS, slippage_bps=SLIPPAGE_BPS,
                              min_events=MIN_FIT_EVENTS, trial_srs=trial_srs,
                              drawdown_cap_r=DRAWDOWN_CAP_R)
        res["h"] = h
        res["n_signals"] = len(fires)
        res["n_trial_srs"] = len(trial_srs)
        rung1.append(res)
        verdict.append(_verdict(res, _rung0_floor(rung0_doc, h)))

    return {
        "config": {
            "deploy": deploy, "horizons": horizons, "n_folds": n_folds,
            "regime_window": REGIME_WINDOW, "n_regimes": N_REGIMES,
            "lockbox_fraction": LOCKBOX_FRACTION, "atr_period": ATR_PERIOD,
            "edge_threshold": EDGE_THRESHOLD, "kelly_scale": KELLY_SCALE,
            "max_fraction": MAX_FRACTION, "taker_bps": TAKER_BPS,
            "slippage_bps": SLIPPAGE_BPS, "min_fit_events": MIN_FIT_EVENTS,
            "drawdown_cap_r": DRAWDOWN_CAP_R, "dsr_threshold": DSR_THRESHOLD,
            "pool_symbols": pool_symbols,
        },
        "rung1": rung1,
        "rung0_floor": {h: _rung0_floor(rung0_doc, h) for h in horizons},
        "verdict": verdict,
    }
