# orderflow_microstructure v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second pre-registered research program (`orderflow_microstructure`) that tests whether short-horizon order-flow dislocation entries on BTC/USDT:USDT 15m perps beat a `donchian_break` control, reusing the existing families, data plumbing, ladder, and bespoke-runner pattern.

**Architecture:** A bespoke domain runner (`orderflow_runner`) drives 10 pre-registered treatment specs (`oi_flush_reversal`, `taker_flow_momentum`, `liquidity_sweep_reclaim`) + 2 unregistered `donchian_break` controls through intraday-tuned ladder gates (screen ≥100, DSR≥0.95 n_trials=10, 6mo/2mo/2mo walk-forward, lockbox ≥20) plus a strict control-dominance check. The dominance math is **entry-pair** (treatment entry vs control entry, same exit/sizing) — distinct from `voltarget`'s sizing-pair — so it lives in a new `orderflow.py` evaluator module that leans on `ladder.r_stream` + `metrics.equity_summary`. No new entry-family code, no new data fetcher, no mutation of frozen ladder constants (intraday floors pass through the stage functions' keyword overrides / local constants).

**Tech Stack:** Python 3, stdlib `unittest` + `pytest`, ccxt (already a dep), sqlite3 (Store), existing MoonFace `research/` + `foundation/` modules.

## Global Constraints

(Verbatim from the frozen spec `docs/research-log/specs/2026-07-02-orderflow-microstructure-design.md`.)

- Symbol/exchange: `binance` / `BTC/USDT:USDT` / timeframe `15m` (`TIMEFRAME_MS["15m"] = 900_000`).
- Exit (frozen): `fixed_bracket{k_stop:2.0, m_tp:1.0, atr_period:14}` (`_BRACKET_MAX_BARS=96` cap dormant).
- Sizing fraction: `0.01` for both treatment and control (`ORDERFLOW_FRACTION`).
- Cost: `COST_FRACTION = 0.001` round-trip (locked; 2× stress reported non-gating).
- Window: `ORDERFLOW_START_MS = 1_598_918_400_000` (2020-09-01 UTC) → run date; `LOCKBOX_FRACTION = 0.2`.
- Gates: screen ≥ **100** trades + expectancy_R>0; holdout MAR>0 & DD≥−0.30 + dominance; DSR ≥ 0.95 with `n_trials = 10`; walk-forward 6mo train / 2mo test / 2mo step (`TRAIN_BARS=17280`, `TEST_BARS=5760`, `STEP_BARS=5760`); lockbox tail MAR≥1.0 & ≥**20** trades & DD≥−0.30 + dominance.
- Kill rule: closed-negative ⇒ no v2, no new family, no gate/exit rescue.
- **Do NOT mutate** `ladder.SCREEN_MIN_TRADES` / `LOCKBOX_MIN_TRADES` / `DSR_THRESHOLD` / `DRAWDOWN_BUDGET` (concluded domains' DSR calibration depends on them). Intraday floors are local constants in `orderflow.py`.
- Git: local trunk-based `main`, never push; commit prefixes `feat(research):` / `docs(research):`; **no** AI-attribution trailer; `docs/` is gitignored so `docs/research-log/*` must be `git add -f`.

---

## File Map

- **Create** `src/moonface/research/orderflow.py` — frozen construction, the 10 treatment specs, 2 control specs, `control_for()`, entry-pair `evaluate_dominant()` / `lockbox_dominant()`, `stage1_of` / `stage2_of` / `stage4_of`, `dominates()`. Pure: imports only `ladder` + `metrics` + `spec`. No store/lockbox imports.
- **Create** `src/moonface/research/orderflow_wf.py` — rolling walk-forward over `r_stream` (no param selection, no calibration): `walk_forward()`, `stage35_of()`. Constants `TRAIN_BARS/TEST_BARS/STEP_BARS` at 15m.
- **Create** `src/moonface/research/orderflow_runner.py` — bespoke runner: `ORDERFLOW_DOMAIN`, `ORDERFLOW_START_MS`, `register()`, `run_domain()`, `_write_verdict()`. Mirrors `voltarget_runner.py`.
- **Modify** `tools/research.py` — import + `cmd_orderflow` + `orderflow` subparser. Mirrors the `voltarget` wiring.
- **Create** `experiments/orderflow_microstructure/PREREGISTRATION.md` — frozen 5-section pre-registration artifact (the user's explicit "pre-register the gates before testing" deliverable).
- **Create** `tests/test_orderflow.py`, `tests/test_orderflow_wf.py`, `tests/test_orderflow_runner.py`; **modify** `tests/test_research_cli.py`.

---

### Task 1: orderflow.py — frozen construction, specs, entry-pair evaluators

**Files:**
- Create: `src/moonface/research/orderflow.py`
- Test: `tests/test_orderflow.py`

**Interfaces:**
- Consumes: `moonface.research.ladder.r_stream(spec, bundle)`, `ladder.DRAWDOWN_BUDGET`, `ladder.LOCKBOX_MIN_MAR`, `ladder.SCREEN_FRACTION`; `moonface.foundation.metrics.equity_summary`, `summarize_r`; `moonface.research.spec.HypothesisSpec`.
- Produces: `ORDERFLOW_DOMAIN`, `ORDERFLOW_FRACTION`, `ORDERFLOW_EXIT`, `N_TRIALS`, `SCREEN_MIN_TRADES_INTRADAY=100`, `LOCKBOX_MIN_TRADES_INTRADAY=20`, `orderflow_specs() -> list[HypothesisSpec]` (10), `control_for(spec) -> HypothesisSpec`, `evaluate_dominant(spec, control_spec, research, screen_fraction=0.7) -> dict`, `lockbox_dominant(spec, control_spec, full, fence_index) -> dict`, `stage1_of(m, min_trades=100)`, `stage2_of(m)`, `stage4_of(m, min_trades=20)`, `dominates(t_mar,t_sharpe,c_mar,c_sharpe)`.

- [ ] **Step 1: Write the failing tests** (`tests/test_orderflow.py`)

```python
# tests/test_orderflow.py
import unittest

from moonface.foundation.bundle import DataBundle
from moonface.research import orderflow as of
from moonface.research.synth import make_candles


class TestSpecGrid(unittest.TestCase):
    def test_ten_treatment_specs_two_controls(self):
        specs = of.orderflow_specs()
        self.assertEqual(len(specs), 10)
        self.assertEqual(of.N_TRIALS, 10)
        families = [s.entry["family"] for s in specs]
        self.assertEqual(families.count("oi_flush_reversal"), 4)
        self.assertEqual(families.count("taker_flow_momentum"), 4)
        self.assertEqual(families.count("liquidity_sweep_reclaim"), 2)
        # oi_flush/taker carry a metrics_field; sweep does not
        oi = [s for s in specs if s.entry["family"] == "oi_flush_reversal"][0]
        self.assertEqual(oi.asset["metrics_field"], "sum_open_interest")
        tk = [s for s in specs if s.entry["family"] == "taker_flow_momentum"][0]
        self.assertEqual(tk.asset["metrics_field"],
                         "sum_taker_long_short_vol_ratio")
        sw = [s for s in specs if s.entry["family"] == "liquidity_sweep_reclaim"][0]
        self.assertNotIn("metrics_field", sw.asset)
        # every treatment spec uses the frozen exit + fraction
        for s in specs:
            self.assertEqual(s.exit["name"], "fixed_bracket")
            self.assertEqual(s.exit["params"],
                             {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0})
            self.assertEqual(s.fraction, of.ORDERFLOW_FRACTION)


class TestControlFor(unittest.TestCase):
    def test_pairs_by_horizon(self):
        spec48 = [s for s in of.orderflow_specs()
                  if s.entry["params"].get("window") == 48
                  or s.entry["params"].get("swing_n") == 48][0]
        spec96 = [s for s in of.orderflow_specs()
                  if s.entry["params"].get("window") == 96
                  or s.entry["params"].get("swing_n") == 96][0]
        c48 = of.control_for(spec48)
        c96 = of.control_for(spec96)
        self.assertEqual(c48.entry["family"], "donchian_break")
        self.assertEqual(c48.entry["params"], {"n": 48, "long_only": False})
        self.assertEqual(c96.entry["params"]["n"], 96)
        # control is a price family: no metrics_field
        self.assertNotIn("metrics_field", c48.asset)


class TestDominates(unittest.TestCase):
    def test_strict_on_mar_and_sharpe(self):
        self.assertTrue(of.dominates(2.0, 0.5, 1.0, 0.4))
        self.assertFalse(of.dominates(2.0, 0.4, 1.0, 0.5))   # sharpe loses
        self.assertFalse(of.dominates(1.0, 0.5, 1.0, 0.5))   # tie -> not strict


class TestStageGates(unittest.TestCase):
    def test_stage1_uses_100_floor(self):
        self.assertTrue(of.stage1_of({"screen_trades": 100,
                                      "screen_expectancy_r": 0.1}))
        self.assertFalse(of.stage1_of({"screen_trades": 99,
                                       "screen_expectancy_r": 0.1}))
        self.assertFalse(of.stage1_of({"screen_trades": 100,
                                       "screen_expectancy_r": 0.0}))

    def test_stage2_needs_mar_budget_dominance(self):
        ok = {"holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
              "holdout_dominance": True}
        self.assertTrue(of.stage2_of(ok))
        self.assertFalse(of.stage2_of({**ok, "holdout_treatment_dd": -0.40}))
        self.assertFalse(of.stage2_of({**ok, "holdout_dominance": False}))

    def test_stage4_lockbox_gate(self):
        ok = {"tail_treatment_mar": 1.0, "tail_treatment_dd": -0.2,
              "tail_trades": 20, "tail_dominance": True}
        self.assertTrue(of.stage4_of(ok))
        self.assertFalse(of.stage4_of({**ok, "tail_treatment_mar": 0.9}))
        self.assertFalse(of.stage4_of({**ok, "tail_trades": 19}))
        self.assertFalse(of.stage4_of({**ok, "tail_dominance": False}))


class TestEvaluateDominant(unittest.TestCase):
    def setUp(self):
        # Flat OI feature -> oi_flush_reversal is silent (sd==0 -> z is None).
        # Shape/determinism only (network-free, no trade count asserted for the
        # control, which is donchian on a synthetic random walk).
        self.candles = make_candles(400, seed=7)
        self.bundle = DataBundle(candles=self.candles, feature=[1000.0] * 400)
        oi = [s for s in of.orderflow_specs()
              if s.entry["family"] == "oi_flush_reversal"][0]
        self.spec = oi
        self.control = of.control_for(oi)

    def test_returns_expected_keys(self):
        m = of.evaluate_dominant(self.spec, self.control, self.bundle)
        for k in ("screen_trades", "screen_expectancy_r", "holdout_trades",
                  "holdout_treatment_mar", "holdout_treatment_dd",
                  "holdout_treatment_sharpe", "holdout_control_mar",
                  "holdout_control_sharpe", "holdout_dominance",
                  "research_sharpe", "research_skew", "research_kurtosis",
                  "research_trades"):
            self.assertIn(k, m)

    def test_flat_feature_treatment_is_silent_and_deterministic(self):
        m = of.evaluate_dominant(self.spec, self.control, self.bundle)
        self.assertEqual(m["screen_trades"], 0)      # flat OI -> no oi_flush entries
        self.assertEqual(m["research_trades"], 0)
        self.assertEqual(
            of.evaluate_dominant(self.spec, self.control, self.bundle), m)

    def test_lockbox_dominant_keys(self):
        m = of.lockbox_dominant(self.spec, self.control, self.bundle, fence_index=320)
        for k in ("tail_trades", "tail_treatment_mar", "tail_treatment_dd",
                  "tail_treatment_sharpe", "tail_control_mar",
                  "tail_control_sharpe", "tail_dominance"):
            self.assertIn(k, m)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_orderflow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.orderflow'`.

- [ ] **Step 3: Write the implementation** (`src/moonface/research/orderflow.py`)

```python
# src/moonface/research/orderflow.py
"""Entry-pair dominance evaluators for the orderflow_microstructure domain
(spec 2026-07-02). Pure functions over ladder.r_stream — no store/lockbox
imports (those live in orderflow_runner).

Unlike voltarget.py (treatment vs control SIZING on the same entries), the
orderflow control is a different ENTRY (donchian_break) at the same sizing,
timeframe, exit, and cost. Dominance = treatment strictly beats the paired
donchian control on BOTH MAR and Sharpe."""
from __future__ import annotations

from moonface.foundation.metrics import equity_summary, summarize_r
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      SCREEN_FRACTION, r_stream)
from moonface.research.spec import HypothesisSpec

ORDERFLOW_DOMAIN = "orderflow_microstructure"

ORDERFLOW_FRACTION = 0.01            # fixed-fractional sizing for both arms
SCREEN_MIN_TRADES_INTRADAY = 100     # intraday floor (ladder.SCREEN_MIN_TRADES=30 untouched)
LOCKBOX_MIN_TRADES_INTRADAY = 20     # intraday floor (ladder.LOCKBOX_MIN_TRADES=10 untouched)
N_TRIALS = 10                        # DSR multiple-comparison correction

# Frozen construction (spec §2).
EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0}
ORDERFLOW_EXIT = (EXIT_NAME, EXIT_PARAMS)

_BTC = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "15m"}
_BTC_OI = {**_BTC, "metrics_field": "sum_open_interest"}
_BTC_TAKER = {**_BTC, "metrics_field": "sum_taker_long_short_vol_ratio"}


def _spec(family: str, params: dict, asset: dict) -> HypothesisSpec:
    return HypothesisSpec(
        domain=ORDERFLOW_DOMAIN, version=1, asset=asset,
        entry={"family": family, "params": params},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=ORDERFLOW_FRACTION)


def orderflow_specs() -> list[HypothesisSpec]:
    """The 10 pre-registered treatment specs (spec §2)."""
    specs: list[HypothesisSpec] = []
    for window in (48, 96):
        for z_thr in (2.0, 2.5):
            specs.append(_spec("oi_flush_reversal",
                               {"window": window, "lookback": 6, "z_thr": z_thr},
                               _BTC_OI))
            specs.append(_spec("taker_flow_momentum",
                               {"window": window, "z_thr": z_thr}, _BTC_TAKER))
    for swing_n in (48, 96):
        specs.append(_spec("liquidity_sweep_reclaim", {"swing_n": swing_n}, _BTC))
    return specs


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    """The donchian_break control paired to a treatment spec by lookback horizon:
    window/swing_n >= 96 -> donchian n=96, else n=48. Same exit/fraction/asset-class."""
    p = spec.entry["params"]
    horizon = p.get("window", p.get("swing_n", 48))
    n = 96 if horizon >= 96 else 48
    return HypothesisSpec(
        domain=ORDERFLOW_DOMAIN, version=1, asset=_BTC,
        entry={"family": "donchian_break", "params": {"n": n, "long_only": False}},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=ORDERFLOW_FRACTION)


def dominates(t_mar: float, t_sharpe: float,
              c_mar: float, c_sharpe: float) -> bool:
    """Strict: treatment beats control on BOTH MAR and Sharpe."""
    return t_mar > c_mar and t_sharpe > c_sharpe


def evaluate_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                      research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    """One pass over the research window for the treatment spec AND its paired
    control. Dominance is computed on the holdout; research_* fields feed DSR."""
    split = int(len(research.candles) * screen_fraction)
    ts = r_stream(spec, research)
    cs = r_stream(control_spec, research)
    t_screen = summarize_r([r for i, r, _ in ts if i < split])
    t_hold = equity_summary([(r, af) for i, r, af in ts if i >= split],
                            ORDERFLOW_FRACTION)
    t_full = equity_summary([(r, af) for _, r, af in ts], ORDERFLOW_FRACTION)
    c_hold = equity_summary([(r, af) for i, r, af in cs if i >= split],
                            ORDERFLOW_FRACTION)
    return {
        "screen_trades": t_screen.trade_count,
        "screen_expectancy_r": t_screen.expectancy_r,
        "holdout_trades": t_hold.trade_count,
        "holdout_treatment_mar": t_hold.mar,
        "holdout_treatment_dd": t_hold.max_drawdown,
        "holdout_treatment_sharpe": t_hold.sharpe,
        "holdout_control_mar": c_hold.mar,
        "holdout_control_sharpe": c_hold.sharpe,
        "holdout_dominance": dominates(t_hold.mar, t_hold.sharpe,
                                       c_hold.mar, c_hold.sharpe),
        "research_sharpe": t_full.sharpe,
        "research_skew": t_full.skew,
        "research_kurtosis": t_full.kurtosis,
        "research_trades": t_full.trade_count,
    }


def lockbox_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                     full, fence_index: int) -> dict:
    """One-touch tail (entry_index >= fence_index) for treatment and control."""
    ts = r_stream(spec, full)
    cs = r_stream(control_spec, full)
    t_tail = equity_summary([(r, af) for i, r, af in ts if i >= fence_index],
                            ORDERFLOW_FRACTION)
    c_tail = equity_summary([(r, af) for i, r, af in cs if i >= fence_index],
                            ORDERFLOW_FRACTION)
    return {
        "tail_trades": t_tail.trade_count,
        "tail_treatment_mar": t_tail.mar,
        "tail_treatment_dd": t_tail.max_drawdown,
        "tail_treatment_sharpe": t_tail.sharpe,
        "tail_control_mar": c_tail.mar,
        "tail_control_sharpe": c_tail.sharpe,
        "tail_dominance": dominates(t_tail.mar, t_tail.sharpe,
                                    c_tail.mar, c_tail.sharpe),
    }


def stage1_of(m: dict, min_trades: int = SCREEN_MIN_TRADES_INTRADAY) -> bool:
    return m["screen_trades"] >= min_trades and m["screen_expectancy_r"] > 0.0


def stage2_of(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def stage4_of(m: dict, min_trades: int = LOCKBOX_MIN_TRADES_INTRADAY) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= min_trades
            and m["tail_dominance"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_orderflow.py -v`
Expected: PASS (all 11 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/orderflow.py tests/test_orderflow.py
git commit -m "feat(research): orderflow entry-pair dominance evaluators + 10-spec grid"
```

---

### Task 2: orderflow_wf.py — rolling walk-forward at 15m

**Files:**
- Create: `src/moonface/research/orderflow_wf.py`
- Test: `tests/test_orderflow_wf.py`

**Interfaces:**
- Consumes: `ladder.r_stream`, `metrics.equity_summary_from_returns`, `metrics.MAX_LEVERAGE`, `orderflow.ORDERFLOW_FRACTION`.
- Produces: `TRAIN_BARS=17280`, `TEST_BARS=5760`, `STEP_BARS=5760`, `walk_forward(spec, research, control_spec, train_bars=TRAIN_BARS, test_bars=TEST_BARS, step_bars=STEP_BARS) -> dict`, `stage35_of(wf) -> bool`.

- [ ] **Step 1: Write the failing tests** (`tests/test_orderflow_wf.py`)

```python
# tests/test_orderflow_wf.py
import unittest

from moonface.foundation.bundle import DataBundle
from moonface.research import orderflow as of
from moonface.research import orderflow_wf as owf
from moonface.research.synth import make_candles


def _sweep_spec():
    # price family -> no feature needed for the walk-forward shape test
    s = [x for x in of.orderflow_specs()
         if x.entry["family"] == "liquidity_sweep_reclaim"][0]
    return s, of.control_for(s)


class TestWalkForwardGeometry(unittest.TestCase):
    def test_fold_count_from_geometry(self):
        n = 17280 + 5760 * 3          # train + 3 test windows
        bundle = DataBundle(candles=make_candles(n, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        expected = len(range(owf.TRAIN_BARS, n - owf.TEST_BARS + 1, owf.STEP_BARS))
        self.assertEqual(wf["folds"], expected)
        self.assertGreaterEqual(expected, 2)

    def test_returns_keys_and_dominance(self):
        n = 17280 + 5760 * 3
        bundle = DataBundle(candles=make_candles(n, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        for k in ("folds", "aggregate_treatment_mar",
                  "aggregate_treatment_sharpe", "aggregate_control_mar",
                  "aggregate_trades", "dominance"):
            self.assertIn(k, wf)

    def test_too_short_yields_no_folds(self):
        bundle = DataBundle(candles=make_candles(1000, seed=3))
        spec, ctrl = _sweep_spec()
        wf = owf.walk_forward(spec, bundle, ctrl)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(owf.stage35_of(wf))


class TestStage35Gate(unittest.TestCase):
    def test_passes_on_positive_mar_and_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_control_mar": 0.1,
              "aggregate_trades": 40, "dominance": True}
        self.assertTrue(owf.stage35_of(ok))

    def test_fails_without_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_control_mar": 0.6,
              "aggregate_trades": 40, "dominance": False}
        self.assertFalse(owf.stage35_of(ok))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_orderflow_wf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.orderflow_wf'`.

- [ ] **Step 3: Write the implementation** (`src/moonface/research/orderflow_wf.py`)

```python
# src/moonface/research/orderflow_wf.py
"""Rolling walk-forward for orderflow_microstructure (spec §4, stage 3.5).

Adapts voltarget_wf's geometry to the entry-pair control-dominance design:
NO param selection and NO calibration (the construction is frozen per spec),
so there is no train window — TRAIN_BARS is only the warm-up offset before
the first test window. Aggregates pooled TEST-window returns for the treatment
spec and its donchian_break control, then checks dominance."""
from __future__ import annotations

from moonface.foundation.bundle import DataBundle
from moonface.foundation.metrics import (MAX_LEVERAGE,
                                         equity_summary_from_returns)
from moonface.research.ladder import r_stream
from moonface.research.orderflow import ORDERFLOW_FRACTION, dominates

_BARS_PER_DAY = 96                           # 15m bars
TRAIN_BARS = 180 * _BARS_PER_DAY             # 6-month warm-up offset (= 17280)
TEST_BARS = 60 * _BARS_PER_DAY               # 2-month test window  (= 5760)
STEP_BARS = TEST_BARS                        # non-overlapping 2-month steps


def _sub_bundle(bundle: DataBundle, lo: int, hi: int) -> DataBundle:
    def cut(seq):
        return seq[lo:hi] if seq is not None else None
    return DataBundle(candles=bundle.candles[lo:hi], funding=cut(bundle.funding),
                      basis=cut(bundle.basis), feature=cut(bundle.feature),
                      bookdepth=cut(bundle.bookdepth))


def walk_forward(spec, research: DataBundle, control_spec,
                 train_bars: int = TRAIN_BARS, test_bars: int = TEST_BARS,
                 step_bars: int = STEP_BARS) -> dict:
    n = len(research.candles)
    trt_returns: list[float] = []
    ctrl_returns: list[float] = []
    folds = 0
    start = train_bars
    while start + test_bars <= n:
        test = _sub_bundle(research, start, start + test_bars)
        for _, r, af in r_stream(spec, test):
            trt_returns.append(min(ORDERFLOW_FRACTION, MAX_LEVERAGE * af) * r)
        for _, r, af in r_stream(control_spec, test):
            ctrl_returns.append(min(ORDERFLOW_FRACTION, MAX_LEVERAGE * af) * r)
        folds += 1
        start += step_bars
    trt = equity_summary_from_returns(trt_returns)
    ctrl = equity_summary_from_returns(ctrl_returns)
    return {
        "folds": folds,
        "aggregate_treatment_mar": trt.mar,
        "aggregate_treatment_sharpe": trt.sharpe,
        "aggregate_control_mar": ctrl.mar,
        "aggregate_trades": trt.trade_count,
        "dominance": dominates(trt.mar, trt.sharpe, ctrl.mar, ctrl.sharpe),
    }


def stage35_of(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_orderflow_wf.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/orderflow_wf.py tests/test_orderflow_wf.py
git commit -m "feat(research): orderflow rolling walk-forward (6mo/2mo/2mo @ 15m)"
```

---

### Task 3: orderflow_runner.py — bespoke domain runner

**Files:**
- Create: `src/moonface/research/orderflow_runner.py`
- Test: `tests/test_orderflow_runner.py`

**Interfaces:**
- Consumes: `store.Store` (`register_domain`, `insert_grid`, `domain`, `rows`, `touch_lockbox`, `set_domain_status`); `lockbox.FencedBundle`; `metrics.deflated_sharpe`; `ladder.DSR_THRESHOLD`, `ladder.SCREEN_FRACTION`; `orderflow.orderflow_specs` / `control_for` / `evaluate_dominant` / `lockbox_dominant` / `stage1_of` / `stage2_of` / `stage4_of` / `N_TRIALS`; `orderflow_wf.walk_forward` / `stage35_of`; `spec.spec_from_json`, `spec.spec_hash`.
- Produces: `ORDERFLOW_DOMAIN`, `ORDERFLOW_START_MS`, `LOCKBOX_FRACTION`, `register(store, now_ms)`, `run_domain(store, loader, out_root) -> "closed_positive" | "closed_negative"`.

- [ ] **Step 1: Write the failing tests** (`tests/test_orderflow_runner.py`)

```python
# tests/test_orderflow_runner.py
import tempfile
import unittest
from pathlib import Path

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.research import orderflow_runner as orunner
from moonface.research.store import Store


def _flat_bundle(asset, start_ms, end_ms):
    """Loader stub: constant price + flat feature -> every family is silent ->
    stage 1 (>=100 trades) fails -> closed_negative, lockbox untouched."""
    n = 6000
    candles = [Candle(i * 900_000, 100.0, 100.0, 100.0, 100.0, 1.0) for i in range(n)]
    return DataBundle(candles=candles, feature=[1000.0] * n)


class TestRegister(unittest.TestCase):
    def test_register_creates_bespoke_domain(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertIsNotNone(d)
            self.assertEqual(d["config"].get("runner"), "orderflow")
            self.assertEqual(d["grid_size"], 10)
            self.assertFalse(d["lockbox_touched"])

    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            orunner.register(store, now_ms=1_800_000_000_000)   # must not overwrite
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertEqual(d["end_ms"], 1_700_000_000_000)


class TestRunDomainNegative(unittest.TestCase):
    def test_flat_data_closes_negative_without_spending_lockbox(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            verdict = orunner.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_negative")
            d = store.domain(orunner.ORDERFLOW_DOMAIN, 1)
            self.assertFalse(d["lockbox_touched"])
            self.assertEqual(d["status"], "closed_negative")
            self.assertTrue((Path(td) / orunner.ORDERFLOW_DOMAIN
                             / "verdict.md").exists())


class TestRunDomainPositive(unittest.TestCase):
    def _stubs(self):
        research_m = {"screen_trades": 120, "screen_expectancy_r": 0.2,
                      "holdout_trades": 40, "holdout_treatment_mar": 0.5,
                      "holdout_treatment_dd": -0.1, "holdout_treatment_sharpe": 0.5,
                      "holdout_control_mar": 0.1, "holdout_control_sharpe": 0.1,
                      "holdout_dominance": True, "research_sharpe": 0.3,
                      "research_skew": 0.0, "research_kurtosis": 3.0,
                      "research_trades": 160}
        wf_m = {"folds": 4, "aggregate_treatment_mar": 0.5,
                "aggregate_treatment_sharpe": 0.4, "aggregate_control_mar": 0.1,
                "aggregate_trades": 40, "dominance": True}
        tail_m = {"tail_trades": 25, "tail_treatment_mar": 1.2,
                  "tail_treatment_dd": -0.2, "tail_treatment_sharpe": 0.6,
                  "tail_control_mar": 0.3, "tail_control_sharpe": 0.2,
                  "tail_dominance": True}
        return research_m, wf_m, tail_m

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            orunner.register(store, now_ms=1_700_000_000_000)
            research_m, wf_m, tail_m = self._stubs()
            with mock.patch.object(orunner, "evaluate_dominant",
                                   return_value=research_m), \
                 mock.patch.object(orunner, "walk_forward",
                                   return_value=wf_m), \
                 mock.patch.object(orunner, "lockbox_dominant",
                                   return_value=tail_m):
                verdict = orunner.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_positive")
            self.assertTrue(store.domain(orunner.ORDERFLOW_DOMAIN, 1)["lockbox_touched"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_orderflow_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.orderflow_runner'`.

- [ ] **Step 3: Write the implementation** (`src/moonface/research/orderflow_runner.py`)

```python
# src/moonface/research/orderflow_runner.py
"""Dedicated runner for the orderflow_microstructure domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) and FencedBundle (one-touch
tail), but drives the entry-pair dominance ladder + walk-forward itself: the
generic runner.run cannot express the donchian_break control-dominance gate.
The generic runner skips any domain whose config.runner is neither None nor
'generic' (the guard in runner.run)."""
from __future__ import annotations

import json
from pathlib import Path

from moonface.foundation.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.research.lockbox import FencedBundle
from moonface.research.orderflow import (N_TRIALS, control_for, evaluate_dominant,
                                        lockbox_dominant, orderflow_specs,
                                        stage1_of, stage2_of, stage4_of)
from moonface.research.orderflow_wf import stage35_of, walk_forward
from moonface.research.spec import spec_from_json, spec_hash
from moonface.research.store import Store

ORDERFLOW_DOMAIN = "orderflow_microstructure"
ORDERFLOW_START_MS = 1_598_918_400_000   # 2020-09-01 UTC (Binance Vision metrics availability)
LOCKBOX_FRACTION = 0.2


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 10-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - ORDERFLOW_START_MS) * LOCKBOX_FRACTION)
    if store.domain(ORDERFLOW_DOMAIN, 1) is None:
        store.register_domain(ORDERFLOW_DOMAIN, 1, "active",
                              {"runner": "orderflow"}, ORDERFLOW_START_MS,
                              now_ms, fence_ts)
        store.insert_grid(ORDERFLOW_DOMAIN, 1, orderflow_specs())


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(ORDERFLOW_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(ORDERFLOW_DOMAIN, 1)]
    grid_size = len(specs)            # == N_TRIALS == 10
    fenced: dict[str, FencedBundle] = {}

    def fb_for(spec):
        key = json.dumps(spec.asset, sort_keys=True)
        if key not in fenced:
            fenced[key] = FencedBundle(
                loader(spec.asset, d["start_ms"], d["end_ms"]), d["fence_ts"])
        return fenced[key]

    # Pass 1: stages 1, 2, 3.5 per spec (with control dominance).
    rows: list[dict] = []
    for spec in specs:
        h = spec_hash(spec)
        fb = fb_for(spec)
        research = fb.research()
        ctrl = control_for(spec)
        m = evaluate_dominant(spec, ctrl, research, SCREEN_FRACTION)
        rows.append({"spec_hash": h, "spec": spec, "m": m, "wf": None,
                     "stage": "research"})
        if not stage1_of(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_of(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward(spec, research, ctrl)
        rows[-1]["wf"] = wf
        if not stage35_of(wf):
            rows[-1]["stage"] = "rejected_wf"
            continue
        rows[-1]["stage"] = "wf_pass"

    # Pass 2: DSR (stage 3) across survivors; trial variance from ALL specs.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    dsr: dict[str, float] = {}
    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        m = r["m"]
        value = deflated_sharpe(m["research_sharpe"], m["research_trades"],
                                m["research_skew"], m["research_kurtosis"],
                                all_sharpes, grid_size)
        r["dsr"] = round(value, 6)
        if r["dsr"] >= DSR_THRESHOLD:
            dsr[r["spec_hash"]] = r["dsr"]
        else:
            r["stage"] = "rejected_dsr"

    # Pass 3: one-touch lockbox (stage 4) for every DSR survivor.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if survivors:
        store.touch_lockbox(ORDERFLOW_DOMAIN, 1)   # set-once for the domain
        for r in survivors:
            fb = fb_for(r["spec"])
            ctrl = control_for(r["spec"])
            tail = lockbox_dominant(r["spec"], ctrl, fb.full, fb.fence_index)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(ORDERFLOW_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows, dsr)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float]) -> None:
    lines = [
        "# orderflow_microstructure v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {ORDERFLOW_DOMAIN} (intraday order-flow microstructure"
        " on BTC/USDT:USDT 15m vs donchian_break control)",
        "- **Construction:** oi_flush_reversal / taker_flow_momentum /"
        " liquidity_sweep_reclaim + fixed_bracket{k_stop:2.0,m_tp:1.0,"
        "atr_period:14}.",
        "- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5,"
        " DSR(>=0.95, n_trials=10), and 4 AND strictly dominate its"
        " donchian_break control on MAR & Sharpe at holdout, WF aggregate,"
        " and lockbox tail.",
        "",
        "| family | final stage | screen n | holdout trt MAR | WF folds |"
        " DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        fam = r["spec"].entry["family"]
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(f"| {fam} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | "
                     f"{dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2, no"
              " added family, no gate/exit relaxation. The intraday-horizon +"
              " reversal-exit lever is terminal for these families on a"
              " closed-negative verdict."]
    d = out_root / ORDERFLOW_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_orderflow_runner.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/orderflow_runner.py tests/test_orderflow_runner.py
git commit -m "feat(research): orderflow bespoke domain runner + verdict writer"
```

---

### Task 4: tools/research.py — `orderflow` CLI subcommand

**Files:**
- Modify: `tools/research.py` (add import near the voltarget import; add `cmd_orderflow` near `cmd_voltarget`; add subparser in `build_parser`).
- Test: `tests/test_research_cli.py` (append a `TestOrderflowCli` class).

**Interfaces:**
- Consumes: `orderflow_runner.ORDERFLOW_DOMAIN`, `register as register_orderflow`, `run_domain as run_orderflow`; `foundation.bundle.load_bundle`.
- Produces: `cmd_orderflow(args)`; an `orderflow` subparser identical in shape to `voltarget`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_research_cli.py`)

Append this class at the end of `tests/test_research_cli.py`:

```python

class TestOrderflowCli(unittest.TestCase):
    def test_parser_wires_orderflow_subcommand(self):
        import tools.research as cli
        args = cli.build_parser().parse_args(["orderflow", "--cache-dir", "/unused"])
        self.assertTrue(callable(args.fn))

    def test_cmd_orderflow_registers_runs_and_prints_verdict(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import tools.research as cli

        args = cli.build_parser().parse_args(
            ["orderflow", "--cache-dir", "/unused",
             "--db", self.db, "--out-root", self.tmp.name])
        with patch("tools.research.register_orderflow") as reg, \
             patch("tools.research.run_orderflow",
                   return_value="closed_negative") as run, \
             patch("tools.research.Store") as store_cls:
            buf = io.StringIO()
            with redirect_stdout(buf):
                args.fn(args)
        reg.assert_called_once()
        run.assert_called_once()
        self.assertIn("closed_negative", buf.getvalue())
```

Also add a `setUp` to this class (the existing `TestCli.setUp` creates `self.tmp`/`self.db`, but this is a separate class):

```python
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "research.db")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_research_cli.py::TestOrderflowCli -v`
Expected: FAIL — `AttributeError: module 'tools.research' has no attribute 'register_orderflow'` (import not added yet).

- [ ] **Step 3: Add the import** (in `tools/research.py`, right after the existing voltarget import block, lines 18–20)

Replace:
```python
from moonface.research.voltarget_runner import (VOLTARGET_DOMAIN,
                                                register as register_voltarget,
                                                run_domain as run_voltarget)
```
with:
```python
from moonface.research.orderflow_runner import (ORDERFLOW_DOMAIN,
                                                register as register_orderflow,
                                                run_domain as run_orderflow)
from moonface.research.voltarget_runner import (VOLTARGET_DOMAIN,
                                                register as register_voltarget,
                                                run_domain as run_voltarget)
```

- [ ] **Step 4: Add `cmd_orderflow`** (in `tools/research.py`, right after `cmd_voltarget`, before `build_parser`)

```python
def cmd_orderflow(args: argparse.Namespace) -> None:
    """Register + run the orderflow_microstructure domain and print the verdict.
    Drives its own entry-pair dominance ladder + walk-forward + one-touch
    lockbox against a donchian_break control."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_orderflow(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_orderflow(store, loader, Path(args.out_root))
    print(f"{ORDERFLOW_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / ORDERFLOW_DOMAIN / 'verdict.md'}")
```

- [ ] **Step 5: Add the subparser** (in `tools/research.py` `build_parser`, right after the `voltarget` subparser block, before `return p`)

```python
    of = sub.add_parser("orderflow",
                        help="register + run orderflow_microstructure"
                             " (intraday order-flow vs donchian_break control,"
                             " BTC/USDT:USDT 15m)")
    of.add_argument("--cache-dir", default=".backtest_cache")
    of.set_defaults(fn=cmd_orderflow)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_research_cli.py -v`
Expected: PASS (the whole file, including the new `TestOrderflowCli`).

- [ ] **Step 7: Commit**

```bash
git add tools/research.py tests/test_research_cli.py
git commit -m "feat(research): orderflow CLI subcommand"
```

---

### Task 5: Frozen PREREGISTRATION artifact + full suite green

**Files:**
- Create: `experiments/orderflow_microstructure/PREREGISTRATION.md`

**Interfaces:**
- Consumes: the frozen spec (`docs/research-log/specs/2026-07-02-orderflow-microstructure-design.md`).
- Produces: the canonical 5-section pre-registration artifact the user asked for ("pre-register the gates before testing"), committed before the first OOS run.

- [ ] **Step 1: Write the artifact** (`experiments/orderflow_microstructure/PREREGISTRATION.md`)

```markdown
# orderflow_microstructure v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Lineage: the MoonFace 4h directional / funding /
positioning program line has closed negative at 4h–daily (e.g.
`funding_fade_voltarget`, closed negative 2026-07-02); the single new lever is
the **intraday horizon** (15m bars + 5m-native order-flow microstructure) with
a reversal-favoring exit and intraday-tuned gates. Design spec:
`docs/research-log/specs/2026-07-02-orderflow-microstructure-design.md`.

## 1. Hypothesis
On BTC/USDT:USDT 15m perps, `oi_flush_reversal` / `taker_flow_momentum` /
`liquidity_sweep_reclaim` + `fixed_bracket{k_stop:2.0,m_tp:1.0,atr_period:14}`
earn positive OOS risk-adjusted return AND strictly beat a `donchian_break`
control on MAR and Sharpe — i.e. the edge that is arbitraged away at 4h
survives at intraday.

## 2. Treatment vs control (the one variable)
- Control: `donchian_break{n:48|96,long_only:False}` (classic trend breakout).
- Treatment: the order-flow family spec, paired by horizon (window/swing_n=48
  ↔ n:48; =96 ↔ n:96). Same 15m timeframe, same `fixed_bracket` exit, same
  `0.01` fraction, same cost — only the **entry signal** differs. Treatment
  grid = 10 specs (oi_flush_reversal ×4, taker_flow_momentum ×4,
  liquidity_sweep_reclaim ×2); controls are reference baselines, not trials.

## 3. Evaluation (hybrid)
Ladder (screen 70% with **≥100-trade** floor + expectancy_R>0; holdout MAR>0
& DD≥−0.30 + dominance; DSR ≥ 0.95 with **n_trials=10**; one-touch lockbox tail
MAR ≥ 1.0 / DD ≥ −0.30 / **≥20 trades** + dominance) + rolling walk-forward
(6mo train-offset / 2mo test / 2mo step at 15m, dominance on aggregate MAR &
Sharpe). Intraday floors pass through the stage functions' keyword overrides /
local constants; the frozen `ladder` constants are **not** mutated. A
treatment spec is eligible only if it dominates its paired control at holdout,
WF aggregate, and lockbox tail.

## 4. Decision
- → PAPER-LIVE WATCHING iff ≥1 treatment spec clears stages 1, 2, 3.5, DSR,
  and 4 AND strictly dominates its `donchian_break` control. The promoting
  family alone goes to watch.
- → CLOSED NEGATIVE otherwise. Kill rule: no v2, no added family, no
  gate/exit relaxation. n_trials = 10.

## 5. Run
`python tools/research.py orderflow`
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS — entire suite green (the four new test files + the modified CLI test, no regressions in the existing ~37 research tests).

- [ ] **Step 3: Commit**

```bash
git add -f experiments/orderflow_microstructure/PREREGISTRATION.md
git commit -m "docs(research): orderflow_microstructure pre-registration artifact"
```

(`experiments/` may be gitignored like `docs/`; use `git add -f` only if `git status` does not list it. Check first: `git status --short experiments/orderflow_microstructure/PREREGISTRATION.md` — if empty, it is ignored and `-f` is required.)

---

### Task 6: Execute the pre-registered program (real data → verdict)

**Files:**
- Produces: `experiments/research/orderflow_microstructure/verdict.md` (and updates the Store db at `experiments/research/research.db`).

**Note (network-bound):** First execution backfills the Binance Vision 5m metrics archive for BTCUSDT (daily zips, ~2100 days since 2020-09-01, cached permanently per day at `.backtest_cache/metrics_BTCUSDT.csv`) and the 15m OHLCV history (ccxt `binanceusdm`, cached at `.backtest_cache/BTC_USDT_15m.csv`). Expect a multi-minute first run; subsequent runs are cache-fast. This is the actual pre-registered OOS evaluation — the frozen gates above are the only thing deciding the verdict.

- [ ] **Step 1: Run the program**

Run: `python tools/research.py orderflow`
Expected output: `orderflow_microstructure v1: closed_positive` **or** `closed_negative`, followed by the verdict path.

- [ ] **Step 2: Read the verdict and record the result**

Open `experiments/research/orderflow_microstructure/verdict.md`. Confirm:
- The per-spec table shows each family's final stage (`rejected_stage1` / `rejected_stage2` / `rejected_wf` / `rejected_dsr` / `lockbox_pass` / `lockbox_fail`).
- `Status` matches the printed verdict.
- The lockbox was touched iff ≥1 spec reached the lockbox stage.

- [ ] **Step 3: Commit the verdict**

```bash
git add -f experiments/research/orderflow_microstructure/verdict.md
git commit -m "docs(research): orderflow_microstructure v1 verdict - <closed_positive|closed_negative>"
```

(Replace `<...>` with the actual verdict. If `experiments/research/` is gitignored, `git add -f`; check with `git status` first.)

- [ ] **Step 4: Update the program memory**

Record the verdict in the auto-memory index per the repo convention (one line in `MEMORY.md` + a dedicated memory file), mirroring the `funding-fade-voltarget-results` entry. State the closed status, which families (if any) survived, and that the intraday-horizon + reversal-exit lever is terminal on a negative verdict.

---

## Self-Review (completed during authoring)

**1. Spec coverage:** §1 hypothesis → Task 1 grid + Task 3 gates; §2 construction → Task 1 (`EXIT_PARAMS`, `_BTC_*`, `orderflow_specs`, `control_for`); §3 treatment-vs-control → Task 1 `evaluate_dominant`/`dominates` + Task 3 wiring; §4 evaluation (screen/holdout/DSR/WF/lockbox + dominance) → Task 1 stage fns + Task 2 WF + Task 3 runner passes; §5 decision/kill rule → Task 3 `promoted`/`_write_verdict` + Task 5 PREREGISTRATION §4; §6 data/window/coverage → Task 3 `ORDERFLOW_START_MS`/`LOCKBOX_FRACTION` (coverage enforced by existing `load_bundle._check_coverage`, no new code); §7 runner architecture → Tasks 1–4; §8 run → Task 6. No gaps.

**2. Placeholder scan:** No TBD/TODO; every code step contains full source; the only `<...>` template is in a commit-message instruction where the value is a runtime output (Task 6, explicitly instructed to substitute the real verdict).

**3. Type consistency:** `evaluate_dominant` / `lockbox_dominant` / `walk_forward` return-dict keys match what `stage1_of`/`stage2_of`/`stage4_of`/`stage35_of` read and what `_write_verdict` reads; the runner imports match the module-level names produced in Tasks 1–2 (`orderflow_specs`, `control_for`, `evaluate_dominant`, `lockbox_dominant`, `stage1_of`, `stage2_of`, `stage4_of`, `N_TRIALS` from `orderflow`; `walk_forward`, `stage35_of` from `orderflow_wf`). The CLI imports (`register_orderflow`, `run_orderflow`, `ORDERFLOW_DOMAIN`) match Task 3's exports.
