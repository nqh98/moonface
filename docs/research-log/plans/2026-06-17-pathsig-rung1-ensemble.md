# Path Signal Rung-1 Regime-Weighted Ensemble Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the rung-1 regime-weighted ensemble of the 16 existing signals — the control rung 2 must beat — scored through the shared dual-frame harness on the same folds as rung 0, with an honest DSR calibration and a head-to-head verdict against the rung-0 floor.

**Architecture:** One new pure-consumer module `src/moonface/research/pathsig/ensemble.py`. Each bar is classified into one of 4 fit-free regime buckets (trend/range × low/high vol) from the frozen features. Per fold, per (signal, regime), the existing rung-0 `fit_distribution` produces a signal-frame `Distribution` and a non-negative edge weight. At each test bar the firing signals' distributions are converted to the market (LONG) frame and weight-averaged into one ensemble `Distribution`, fed to the shared `decide` → `evaluate_strategy`. A `ensemble` CLI subcommand wires the real readers and reports rung 1 against the rung-0 floor.

**Tech Stack:** Python 3.11, standard library only (`statistics`), `pytest`, `ruff`. Reuses `moonface.research.pathsig.baseline` (`fit_distribution`, `SIGNALS`, `POOL_SYMBOLS`, `_METRICS_FIELD`, policy constants), `pathsig.data.build_btc_dataset`, `pathsig.{policy,evaluate,walkforward,features,dataset}`, `moonface.research.entries.generate_entries`, `moonface.research.bundle.DataBundle`.

Design spec: `docs/research-log/specs/2026-06-17-pathsig-rung1-ensemble-design.md`

---

## File Structure

- Create: `src/moonface/research/pathsig/ensemble.py` — `assign_regimes` (+ `_trailing_rank`), `cell_weight`, `_to_market`, `ensemble_distribution`, `replay_ensemble`, `run_ensemble_to_doc` (+ `_trial_srs_from_rung0`, `_rung0_floor`, `_verdict`), regime constants.
- Modify: `tools/path_signal.py` — add the `ensemble` subcommand.
- Test: `tests/test_pathsig_ensemble.py`.
- Generated (force-add, gitignore convention): `experiments/path_signal/rung1_ensemble.json`.

Tests are flat (repo convention) and read in isolation; helpers are defined inline in the test file.

---

## Task 1: Regime classifier

**Files:**
- Create: `src/moonface/research/pathsig/ensemble.py`
- Test: `tests/test_pathsig_ensemble.py`

`assign_regimes` labels each bar with a 4-bucket regime id (`trend_bit*2 + vol_bit`) from point-in-time trailing percentile ranks of `rvol_24` and `abs(ma100_dist)`. Ranks use only strictly-prior samples, so nothing is fit and no future bar affects an earlier label.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_ensemble.py
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.ensemble import _trailing_rank, assign_regimes
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel

_RVOL = FEATURE_NAMES.index("rvol_24")
_MA = FEATURE_NAMES.index("ma100_dist")


def _sample(index, rvol=0.0, ma=0.0):
    x = [0.0] * len(FEATURE_NAMES)
    x[_RVOL] = rvol
    x[_MA] = ma
    x[FEATURE_NAMES.index("atr_frac")] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(0.0, 0.0, 0.0))


def test_trailing_rank_is_point_in_time():
    vals = [1.0, 2.0, 3.0, 0.5]
    assert _trailing_rank(vals, 0, 180) == 0.0          # no prior -> 0.0
    assert _trailing_rank(vals, 2, 180) == 1.0          # 3.0 beats 1.0, 2.0
    assert _trailing_rank(vals, 3, 180) == 0.0          # 0.5 below all priors


def test_assign_regimes_buckets_and_point_in_time():
    # rising rvol and |ma| so late bars rank high on both axes -> regime 3
    samples = [_sample(i, rvol=float(i), ma=float(i)) for i in range(50)]
    regimes = assign_regimes(samples, window=180)
    assert set(regimes) <= {0, 1, 2, 3}
    assert regimes[0] == 0                               # no prior -> low/range
    assert regimes[-1] == 3                              # high vol + trend
    # a late spike must not change an earlier bar's regime
    before = list(regimes)
    samples2 = samples + [_sample(999, rvol=1e9, ma=1e9)]
    assert assign_regimes(samples2, window=180)[:50] == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: FAIL (module `ensemble` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/ensemble.py`:

```python
"""Rung-1 regime-weighted ensemble of the existing signal families.

Each bar is classified into one of 4 fit-free regime buckets (trend/range x
low/high vol) from the frozen features. Per fold, per (signal, regime), the
rung-0 fit_distribution gives a signal-frame Distribution and a non-negative
edge weight; at each test bar the firing signals' distributions are converted to
the market (LONG) frame and weight-averaged into one ensemble Distribution, fed
to the shared decide() -> evaluate_strategy(). The control rung 2 must beat.
Design frozen in docs/research-log/specs/2026-06-17-pathsig-rung1-ensemble-design.md."""
from __future__ import annotations

from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.policy import Distribution

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/ensemble.py tests/test_pathsig_ensemble.py
git commit -m "feat(pathsig): rung-1 fit-free regime classifier"
```

---

## Task 2: Cell weighting, market conversion, and blend

**Files:**
- Modify: `src/moonface/research/pathsig/ensemble.py`
- Test: `tests/test_pathsig_ensemble.py`

`cell_weight` turns a fitted distribution into a non-negative edge weight; `_to_market` reframes a signal-frame distribution to the market (LONG) frame given the fired side; `ensemble_distribution` weight-averages market-frame contributions (None when no positive weight).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_ensemble.py`:

```python
from moonface.research.pathsig.ensemble import (cell_weight, _to_market,
                                                ensemble_distribution)
from moonface.research.pathsig.policy import Distribution


def test_cell_weight_clamps_non_positive_and_none():
    assert cell_weight(None) == 0.0
    assert cell_weight(Distribution(0.5, 0.0, 0.0, 0.0)) == 0.0      # mae 0
    assert cell_weight(Distribution(0.5, -1.0, -2.0, 1.0)) == 0.0    # edge < 0
    w = cell_weight(Distribution(0.6, 1.0, -2.0, 3.0))
    assert w == 0.5                                                   # 1.0 / 2.0


def test_to_market_short_flips_frame():
    d = Distribution(p_up=0.7, exp_ret_r=1.0, exp_mae_r=-0.5, exp_mfe_r=2.0)
    assert _to_market(d, "LONG") == d
    m = _to_market(d, "SHORT")
    assert m.p_up == 0.3 and m.exp_ret_r == -1.0
    assert m.exp_mae_r == -2.0 and m.exp_mfe_r == 0.5


def test_ensemble_distribution_weight_average_and_netting():
    long_d = Distribution(0.7, 1.0, -1.0, 2.0)
    short_d = Distribution(0.7, 1.0, -1.0, 2.0)     # same in its own frame
    # opposing equal-weight signals net toward zero drift
    ens = ensemble_distribution([(_to_market(long_d, "LONG"), 1.0),
                                 (_to_market(short_d, "SHORT"), 1.0)])
    assert ens.exp_ret_r == 0.0
    assert ens.p_up == 0.5
    assert ensemble_distribution([]) is None
    assert ensemble_distribution([(long_d, 0.0)]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: FAIL (`cell_weight` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/ensemble.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/ensemble.py tests/test_pathsig_ensemble.py
git commit -m "feat(pathsig): rung-1 cell weighting and market-frame blend"
```

---

## Task 3: Ensemble fold replay

**Files:**
- Modify: `src/moonface/research/pathsig/ensemble.py`
- Test: `tests/test_pathsig_ensemble.py`

`replay_ensemble` runs the fold loop: per fold it fits per-(signal, regime) cells on the train block (rung-0 `fit_distribution`), then at each test bar where any signal fires it blends the contributing cells into the ensemble decision and scores the concatenated stream under both frames.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_ensemble.py`:

```python
from moonface.research.pathsig.ensemble import replay_ensemble
from moonface.research.pathsig.walkforward import Fold


def _wall_sample(index):
    x = [0.0] * len(FEATURE_NAMES)
    x[FEATURE_NAMES.index("atr_frac")] = 0.02
    return Sample(index=index, timestamp_ms=index, x=x,
                  label=PathLabel(ret_r=0.4, mae_r=-1.0, mfe_r=0.8))


def test_replay_ensemble_reports_both_frames():
    samples = [_wall_sample(i) for i in range(60)]
    regimes = [0] * 60                              # single regime
    fires = {0: {i: "LONG" for i in range(60)}}     # one signal, always LONG
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_ensemble(samples, folds, regimes, fires, edge_threshold=0.05,
                          kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                          slippage_bps=2.0, min_events=10, trial_srs=[0.1, 0.2],
                          drawdown_cap_r=15.0)
    assert res["status"] == "ok"
    assert "risk_adjusted" in res and "fixed_cap" in res
    assert res["n_trades"] >= 1
    assert isinstance(res["fixed_cap"]["within_cap"], bool)


def test_replay_ensemble_waits_when_no_cells_fit():
    samples = [_wall_sample(i) for i in range(60)]
    regimes = [0] * 60
    fires = {0: {0: "LONG"}}                         # only one fired bar -> below min_events
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_ensemble(samples, folds, regimes, fires, edge_threshold=0.05,
                          kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                          slippage_bps=2.0, min_events=10, trial_srs=[],
                          drawdown_cap_r=15.0)
    assert res["status"] == "no_trades"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: FAIL (`replay_ensemble` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/ensemble.py` (add these imports to the top of the file: `from moonface.research.pathsig.baseline import fit_distribution`, `from moonface.research.pathsig.evaluate import evaluate_strategy`, `from moonface.research.pathsig.policy import Decision, decide`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/ensemble.py tests/test_pathsig_ensemble.py
git commit -m "feat(pathsig): rung-1 ensemble fold replay"
```

---

## Task 4: Run document + rung-0 verdict

**Files:**
- Modify: `src/moonface/research/pathsig/ensemble.py`
- Test: `tests/test_pathsig_ensemble.py`

`run_ensemble_to_doc` is the offline-testable entry point: per horizon it builds the BTC Sample grid + folds + regimes, resolves each signal's fire-map (swapping in positioning metrics fields), pulls the honest `trial_srs` from the rung-0 artifact, replays the ensemble, and assembles the head-to-head document.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_ensemble.py`:

```python
from moonface.models import Candle
from moonface.research.pathsig.ensemble import run_ensemble_to_doc

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_run_ensemble_to_doc_schema_and_verdict():
    rung0 = {"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}
    doc = run_ensemble_to_doc(_readers(500), n_folds=2, horizons=[6],
                              pool_symbols=["ETHUSDT"], rung0_doc=rung0)
    assert doc["config"]["horizons"] == [6]
    r1 = doc["rung1"][0]
    assert r1["h"] == 6 and r1["status"] in {"ok", "no_trades"}
    v = doc["verdict"][0]
    assert isinstance(v["beats_rung0"], bool)
    assert isinstance(v["clears_gate"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: FAIL (`run_ensemble_to_doc` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/ensemble.py` (add these imports to the top: `from moonface.research.bundle import DataBundle`, `from moonface.research.entries import UnknownEntryFamily, generate_entries`, `from moonface.research.pathsig.baseline import (ATR_PERIOD, DRAWDOWN_CAP_R, EDGE_THRESHOLD, KELLY_SCALE, LOCKBOX_FRACTION, MAX_FRACTION, MIN_FIT_EVENTS, POOL_SYMBOLS, SIGNALS, SLIPPAGE_BPS, TAKER_BPS, _METRICS_FIELD)`, `from moonface.research.pathsig.data import build_btc_dataset`, `from moonface.research.pathsig.walkforward import walk_forward_folds`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_ensemble.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/ensemble.py tests/test_pathsig_ensemble.py
git commit -m "feat(pathsig): rung-1 run document with rung-0 verdict"
```

---

## Task 5: `ensemble` CLI subcommand

**Files:**
- Modify: `tools/path_signal.py`
- Test: `tests/test_pathsig_ensemble_cli.py`

The subcommand wires the real CSV readers, loads the rung-0 artifact for the DSR calibration + floor, and writes the document. A `readers` injection point keeps the test offline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_ensemble_cli.py
import json
import sys
from pathlib import Path

from moonface.models import Candle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import path_signal  # noqa: E402

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_ensemble_writes_results_json(tmp_path):
    rung0 = tmp_path / "rung0.json"
    rung0.write_text(json.dumps({"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}))
    out = tmp_path / "rung1.json"
    path_signal.ensemble(str(out), cache_dir=".backtest_cache", n_folds=2,
                         horizons=[6], rung0_path=str(rung0),
                         readers=_readers(500), pool_symbols=["ETHUSDT"])
    doc = json.loads(out.read_text())
    assert doc["config"]["horizons"] == [6]
    assert doc["rung1"] and doc["verdict"]
    assert "beats_rung0" in doc["verdict"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_ensemble_cli.py -v`
Expected: FAIL (`path_signal.ensemble` not defined).

- [ ] **Step 3: Write the implementation**

In `tools/path_signal.py`, add the `ensemble` function after `baseline`:

```python
def ensemble(out_path: str, cache_dir: str, n_folds: int,
             horizons: list[int], rung0_path: str | None = None,
             readers=None, pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import POOL_SYMBOLS
    from moonface.research.pathsig.ensemble import run_ensemble_to_doc

    rung0_doc = None
    if rung0_path and Path(rung0_path).exists():
        rung0_doc = json.loads(Path(rung0_path).read_text())
    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_ensemble_to_doc(readers, n_folds=n_folds, horizons=horizons,
                              pool_symbols=pool_symbols or POOL_SYMBOLS,
                              rung0_doc=rung0_doc)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    print(f"wrote {out_path}")
    for res, v in zip(doc["rung1"], doc["verdict"]):
        if res["status"] != "ok":
            print(f"  h={res['h']} {res['status']}")
            continue
        fc, ra = res["fixed_cap"], res["risk_adjusted"]
        print(f"  h={res['h']} trades={res['n_trades']} "
              f"total_r={fc['total_r']:+.2f} maxdd_r={fc['max_drawdown_r']:+.2f} "
              f"cap_ok={fc['within_cap']} dsr={ra['dsr']:.3f} "
              f"beats_rung0={v['beats_rung0']} clears_gate={v['clears_gate']}")
```

Then register the subcommand in `main`. Add this block after the `baseline` subparser setup (after the `bl.add_argument("--horizons", ...)` line) and before `args = parser.parse_args(argv)`:

```python
    en = sub.add_parser("ensemble", help="run the rung-1 regime ensemble")
    en.add_argument("--out", default="experiments/path_signal/rung1_ensemble.json")
    en.add_argument("--rung0", default="experiments/path_signal/rung0_baseline.json")
    en.add_argument("--cache-dir", default=".backtest_cache")
    en.add_argument("--n-folds", type=int, default=5)
    en.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
```

And add this dispatch branch in `main`, immediately before the final `return 1`:

```python
    if args.cmd == "ensemble":
        ensemble(args.out, args.cache_dir, args.n_folds, args.horizons,
                 rung0_path=args.rung0)
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_ensemble_cli.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add tools/path_signal.py tests/test_pathsig_ensemble_cli.py
git commit -m "feat(pathsig): ensemble CLI subcommand"
```

---

## Task 6: Generate the artifact + full verification

**Files:**
- Generated: `experiments/path_signal/rung1_ensemble.json`

- [ ] **Step 1: Run the whole suite + lint**

Run: `python -m pytest tests/ -q && ruff check src/moonface/research/pathsig tools/path_signal.py`
Expected: all tests PASS, ruff reports no issues.

- [ ] **Step 2: Generate the real rung-1 result over the cached data**

Run: `python tools/path_signal.py ensemble --out experiments/path_signal/rung1_ensemble.json --rung0 experiments/path_signal/rung0_baseline.json --n-folds 5 --horizons 6 12`
Expected: writes the JSON and prints a per-horizon line with `total_r`, `dsr`, `beats_rung0`, `clears_gate`. Read the `verdict` against the spec's §6: the expected-and-useful outcome is `beats_rung0=true` (the floor is ~nil) with `clears_gate=false` ("ensembling helps but is not deflation-significant"). A `clears_gate=true` here would be the first deflation-significant result in the program — investigate before celebrating (check trade count, regime cell coverage, that the lockbox stayed sealed).

- [ ] **Step 3: Commit the artifact (force-add — experiments specs are tracked despite global gitignore)**

```bash
git add -f experiments/path_signal/rung1_ensemble.json
git commit -m "chore(pathsig): rung-1 ensemble results artifact"
```

---

## Self-Review

**Spec coverage** (against `docs/research-log/specs/2026-06-17-pathsig-rung1-ensemble-design.md`):
- §2 one pure-consumer module, no frozen interface changed → Tasks 1–4 only consume rung-0/foundations functions. ✅
- §3 4-bucket fit-free trailing-rank regime, direction not an axis, indices via `FEATURE_NAMES.index` → Task 1. ✅
- §4 per-(signal, regime) `fit_distribution` + non-negative edge weight + `MIN_FIT_EVENTS` drop + positioning metrics-field swap → Tasks 2 (`cell_weight`) + 3 (fold fit) + 4 (field swap). ✅
- §5 market-frame conversion + weight-normalized blend + WAIT on no weight + LONG-frame label for realized R → Tasks 2 (`_to_market`/`ensemble_distribution`) + 3 (test-bar loop). ✅
- §6 identical folds + lockbox sealed + honest `trial_srs` from rung-0 artifact + two-part verdict → Tasks 3 (`walk_forward_folds`, `trial_srs` passthrough) + 4 (`_trial_srs_from_rung0`, `_verdict`). ✅
- §7 `ensemble` CLI + JSON schema + stdout table + offline `readers` injection → Task 5. ✅
- §8 tests (regime point-in-time, weighting clamp, blend netting, leak guard via fit_distribution train-only, end-to-end schema, CLI) → Tasks 1–5 tests. ✅
- §9 out of scope (no learned model, no grid, lockbox sealed, no new features) → none of the tasks add these. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command states expected output. ✅

**Type consistency:** `Distribution`/`Decision`/`Sample`/`Fold`/`PathLabel` used exactly as defined; `fit_distribution`/`evaluate_strategy`/`decide` signatures match their rung-0/foundations definitions; `_trailing_rank`→`assign_regimes`→`replay_ensemble`→`run_ensemble_to_doc`→`ensemble` form a consistent call chain; constants (`EDGE_THRESHOLD`, `MIN_FIT_EVENTS`, `_METRICS_FIELD`, `SIGNALS`, `POOL_SYMBOLS`, `ATR_PERIOD`, `LOCKBOX_FRACTION`) are imported from `baseline`, not redefined. `_to_market` mirrors a `Distribution` (distinct from rung-0 `_mirror`, which mirrors a `PathLabel`) — intentional, both correct. `n_trials=max(1, len(trial_srs))` guards the empty-`trial_srs` fallback noted in §6. ✅

**Leak-guard note:** the regime is point-in-time (Task 1 test), cell fits use train positions only (rung-0 `fit_distribution`), the embargo/lockbox are enforced by the reused `walk_forward_folds`, and `trial_srs` is read from the already-sealed rung-0 run — no test-fold or lockbox information enters any fit. ✅
