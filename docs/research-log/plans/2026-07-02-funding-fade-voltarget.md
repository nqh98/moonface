# funding_fade_voltarget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and wire the pre-registered `funding_fade_voltarget` research program — a paired test of whether per-trade vol/risk-targeted sizing beats fixed-fractional sizing on `funding_fade + fixed_bracket` for ETH/SOL, under the hybrid ladder + rolling walk-forward + one-touch lockbox.

**Architecture:** A dedicated evaluator (`voltarget.py` sizer/paired-eval + `voltarget_wf.py` walk-forward) operates on the existing `(entry_index, net_R, atr_frac)` stream from `ladder.r_stream`. A dedicated runner (`voltarget_runner.py`) drives the paired ladder + WF + one-touch lockbox, reusing `Store` (registration + `touch_lockbox`) and `FencedBundle` (one-touch tail). The generic `runner.run` gains a one-line guard to skip bespoke-runner domains. A `voltarget` CLI subcommand registers + runs + prints the verdict. The treatment sizes via `equity_summary_from_returns` (per-trade returns); the control via the existing `equity_summary(trades, fraction)`.

**Tech Stack:** Python 3, stdlib only (no new deps); `pytest`; existing MoonFace modules (`foundation.metrics`, `foundation.bundle`, `research.ladder`, `research.lockbox`, `research.store`, `research.spec`).

## Global Constraints

Copied verbatim from the spec (`docs/research-log/specs/2026-07-02-funding-fade-voltarget-design.md`) and the existing code:

- **Frozen construction:** entry `funding_fade {window: 60, z_thr: 1.5}`; exit `fixed_bracket {atr_period: 14, k_stop: 2.0, m_tp: 4.0}`. `n_trials = 2` (ETH, SOL). No second vol lookback, no fraction grid, no exit/entry variation, no budget relaxation.
- **Assets:** `ETH/USDT:USDT` and `SOL/USDT:USDT`, 4h, Binance, each with `funding_symbol`. BTC excluded (contaminated).
- **Sizing:** control `CONTROL_FRACTION = 0.01`. Treatment `f_i = clamp(target_risk / atr_frac_i, 0, MAX_LEVERAGE * atr_frac_i)` with `MAX_LEVERAGE = 5.0`; `target_risk` calibrated so `mean(f_i over screen) = 0.01` (iso-average-risk).
- **Gate thresholds (from `research/ladder.py`):** `SCREEN_FRACTION = 0.7`, `SCREEN_MIN_TRADES = 30`, `DSR_THRESHOLD = 0.95`, `LOCKBOX_MIN_MAR = 1.0`, `LOCKBOX_MIN_TRADES = 10`, `DRAWDOWN_BUDGET = -0.30`. `COST_FRACTION = 0.001`.
- **Window:** `VOLTARGET_START_MS = 1_577_836_800_000` (2020-01-01 UTC) → registration `now_ms`; lockbox fence = final `LOCKBOX_FRACTION = 0.2` of the window.
- **Walk-forward geometry (4h = 6 bars/day):** `TRAIN_BARS = 6570` (3 yr), `TEST_BARS = 1095` (6 mo), `STEP_BARS = 1095`, within the research window only.
- **Verdict:** `closed_positive` iff BOTH assets clear stages 1, 2, 3 (DSR), 3.5 (WF), 4 (lockbox) AND the treatment strictly dominates the control on MAR & Sharpe at holdout, WF aggregate, and lockbox tail. Else `closed_negative`. Lockbox one-touch; `touch_lockbox` is spent only after stages 1–3.5 clear for every spec.
- **Git (MoonFace workflow):** local trunk-based `main`; never push to origin; no `Co-Authored-By`/AI trailer in commits; `docs/research-log/*` is force-tracked (`git add -f`) because `~/.gitignore_global` ignores `docs/`.
- **Tests:** `pytest` from repo root (`testpaths = ["tests"]`). Source is `src/`-layout; tests import `moonface.*` directly. Synthetic fixtures via `research.synth.make_candles`.

## File Structure

- **Create `src/moonface/research/voltarget.py`** — sizer primitives (`vol_fraction`, `calibrate_target_risk`, `treatment_returns`, `paired_dominance`), paired evaluators (`evaluate_paired`, `paired_research`, `paired_lockbox`), and paired stage gates (`stage1_paired`, `stage2_paired`, `stage4_paired`). Pure functions over the `r_stream` trade stream; no store/lockbox imports.
- **Create `src/moonface/research/voltarget_wf.py`** — `walk_forward_paired` + `stage35_paired`. Rolling train/test folds, per-fold `target_risk` calibration, pooled test-window returns for both arms.
- **Create `src/moonface/research/voltarget_runner.py`** — `voltarget_specs`, `register`, `run_domain`, verdict writer. Orchestrates stages 1→4 + WF + DSR + one-touch lockbox via `Store` + `FencedBundle`.
- **Modify `src/moonface/research/runner.py`** — one-line guard: skip domains whose `config["runner"]` is neither `None` nor `"generic"`.
- **Modify `tools/research.py`** — add `voltarget` subcommand (`cmd_voltarget`) + `--cache-dir`.
- **Create `experiments/funding_fade_voltarget/PREREGISTRATION.md`** — the frozen, human-readable pre-registration artifact.
- **Create `tests/test_voltarget.py`** — Tasks 1–2 unit tests.
- **Create `tests/test_voltarget_wf.py`** — Task 3 tests.
- **Create `tests/test_voltarget_runner.py`** — Task 4 tests.
- **Modify `tests/test_research_runner.py`** — Task 5 guard test.

---

### Task 1: voltarget sizer primitives

**Files:**
- Create: `src/moonface/research/voltarget.py`
- Test: `tests/test_voltarget.py`

**Interfaces:**
- Consumes: `moonface.foundation.metrics` (`EquitySummary`, `MAX_LEVERAGE`, `equity_summary`, `equity_summary_from_returns`, `summarize_r`); `moonface.research.ladder` (`DRAWDOWN_BUDGET`, `LOCKBOX_MIN_MAR`, `LOCKBOX_MIN_TRADES`, `SCREEN_FRACTION`, `SCREEN_MIN_TRADES`, `r_stream`).
- Produces: `vol_fraction(atr_frac, target_risk) -> float`; `calibrate_target_risk(atr_fracs, mean_fraction=ISO_MEAN_FRACTION) -> float`; `treatment_returns(trades, target_risk) -> list[float]`; `paired_dominance(treatment, control) -> bool`; constants `CONTROL_FRACTION`, `ISO_MEAN_FRACTION`, `VOLTARGET_ENTRY`, `VOLTARGET_EXIT`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voltarget.py`:

```python
# tests/test_voltarget.py
import unittest

from moonface.foundation.metrics import EquitySummary
from moonface.research import voltarget


class TestVolFraction(unittest.TestCase):
    def test_equalizes_stop_risk_and_clamps(self):
        # raw = target_risk / atr_frac; cap = MAX_LEVERAGE * atr_frac
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 0.0002), 0.01)   # raw=0.01
        self.assertAlmostEqual(voltarget.vol_fraction(0.01, 0.0001), 0.01)   # raw=0.01
        # huge target_risk saturates at the leverage cap (5.0 * atr_frac)
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 10.0), 0.10)     # cap=5*0.02
        # zero target_risk -> zero fraction
        self.assertAlmostEqual(voltarget.vol_fraction(0.02, 0.0), 0.0)

    def test_floor_is_zero(self):
        self.assertGreaterEqual(voltarget.vol_fraction(0.05, 1.0), 0.0)


class TestCalibrateTargetRisk(unittest.TestCase):
    def test_mean_fraction_matches_control(self):
        afs = [0.01, 0.02, 0.005, 0.015]  # varied vols, none saturating at cap
        tr = voltarget.calibrate_target_risk(afs, mean_fraction=0.01)
        mean_f = sum(voltarget.vol_fraction(af, tr) for af in afs) / len(afs)
        self.assertAlmostEqual(mean_f, 0.01, places=6)

    def test_monotone_unique_root(self):
        afs = [0.01, 0.02, 0.03]
        tr = voltarget.calibrate_target_risk(afs, mean_fraction=0.02)
        # double the target -> mean at least as large (non-decreasing)
        tr2 = voltarget.calibrate_target_risk(afs, mean_fraction=0.04)
        m1 = sum(voltarget.vol_fraction(af, tr) for af in afs) / len(afs)
        m2 = sum(voltarget.vol_fraction(af, tr2) for af in afs) / len(afs)
        self.assertLessEqual(m1, m2 + 1e-9)

    def test_empty_returns_zero(self):
        self.assertEqual(voltarget.calibrate_target_risk([]), 0.0)


class TestTreatmentReturns(unittest.TestCase):
    def test_sizes_each_trade_by_vol(self):
        trades = [(1.0, 0.02), (-1.0, 0.01)]   # (R, atr_frac)
        tr = 0.0002
        rets = voltarget.treatment_returns(trades, tr)
        self.assertEqual(len(rets), 2)
        self.assertAlmostEqual(rets[0], voltarget.vol_fraction(0.02, tr) * 1.0)
        self.assertAlmostEqual(rets[1], voltarget.vol_fraction(0.01, tr) * -1.0)


class TestPairedDominance(unittest.TestCase):
    def _es(self, mar, sharpe):
        return EquitySummary(trade_count=10, net_return=mar, max_drawdown=-0.1,
                             mar=mar, sharpe=sharpe, skew=0.0, kurtosis=3.0)

    def test_strict_on_both(self):
        self.assertTrue(voltarget.paired_dominance(self._es(2.0, 0.5),
                                                    self._es(1.0, 0.4)))
        # wins MAR only -> not dominant
        self.assertFalse(voltarget.paired_dominance(self._es(2.0, 0.4),
                                                     self._es(1.0, 0.5)))
        # tie -> not dominant (strict)
        self.assertFalse(voltarget.paired_dominance(self._es(1.0, 0.5),
                                                     self._es(1.0, 0.5)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voltarget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.voltarget'`

- [ ] **Step 3: Write minimal implementation**

Create `src/moonface/research/voltarget.py`:

```python
# src/moonface/research/voltarget.py
"""Vol/risk-targeted sizing for funding_fade + fixed_bracket (spec 2026-07-02).

The treatment sizes each trade so stop-risk is constant (notional inversely
proportional to ATR), iso-average-risk calibrated to the fixed-fractional
control. Pure functions over the (entry_index, net_R, atr_frac) stream from
ladder.r_stream; sizing math only — no entry/exit logic of its own, and no
store/lockbox imports (those live in voltarget_runner)."""
from __future__ import annotations

from moonface.foundation.metrics import (EquitySummary, MAX_LEVERAGE,
                                         equity_summary,
                                         equity_summary_from_returns,
                                         summarize_r)
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      LOCKBOX_MIN_TRADES, SCREEN_FRACTION,
                                      SCREEN_MIN_TRADES, r_stream)

CONTROL_FRACTION = 0.01            # fixed-fractional baseline (== funding_fade_transfer)
ISO_MEAN_FRACTION = 0.01           # treatment calibrated so mean(f_i) == this

# Frozen construction (spec §4).
VOLTARGET_ENTRY = ("funding_fade", {"window": 60, "z_thr": 1.5})
VOLTARGET_EXIT = ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0})


def vol_fraction(atr_frac: float, target_risk: float) -> float:
    """Per-trade notional fraction that equalizes stop-risk: target_risk/atr_frac,
    clamped to [0, MAX_LEVERAGE*atr_frac] (the program's leverage clamp)."""
    raw = target_risk / atr_frac
    return max(0.0, min(raw, MAX_LEVERAGE * atr_frac))


def calibrate_target_risk(atr_fracs: list[float],
                          mean_fraction: float = ISO_MEAN_FRACTION) -> float:
    """Scalar target_risk s.t. mean(vol_fraction(af, target_risk)) == mean_fraction.
    vol_fraction is non-decreasing in target_risk, so a unique root exists when
    the saturated mean (MAX_LEVERAGE*mean(af)) reaches mean_fraction."""
    if not atr_fracs or mean_fraction <= 0.0:
        return 0.0

    def mean_at(tr: float) -> float:
        return sum(vol_fraction(af, tr) for af in atr_fracs) / len(atr_fracs)

    hi = mean_fraction
    while mean_at(hi) < mean_fraction and hi < 1.0:
        hi *= 2.0
    if mean_at(hi) < mean_fraction:
        raise ValueError("iso-average-risk target unreachable under the leverage clamp")
    lo = 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mean_at(mid) < mean_fraction:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def treatment_returns(trades: list[tuple[float, float]],
                      target_risk: float) -> list[float]:
    """Per-trade sized returns f_i * R_i for the vol-targeted treatment."""
    return [vol_fraction(af, target_risk) * r for r, af in trades]


def paired_dominance(treatment: EquitySummary,
                     control: EquitySummary) -> bool:
    """Strict: treatment beats control on BOTH MAR and Sharpe."""
    return treatment.mar > control.mar and treatment.sharpe > control.sharpe
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voltarget.py -v`
Expected: PASS (all 4 test classes green).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/voltarget.py tests/test_voltarget.py
git commit -m "feat(research): vol-target sizer primitives for funding_fade_voltarget"
```

---

### Task 2: paired research + lockbox evaluators

**Files:**
- Modify: `src/moonface/research/voltarget.py` (append evaluators + gates)
- Test: `tests/test_voltarget.py` (append)

**Interfaces:**
- Consumes: Task 1 primitives; `equity_summary`, `equity_summary_from_returns`, `summarize_r`; `r_stream`.
- Produces: `evaluate_paired(stream, split_index, control_fraction=CONTROL_FRACTION) -> dict`; `stage1_paired(m) -> bool`; `stage2_paired(m) -> bool`; `paired_research(spec, research, screen_fraction=SCREEN_FRACTION) -> dict`; `paired_lockbox(spec, full, fence_index, screen_fraction=SCREEN_FRACTION) -> dict`; `stage4_paired(m) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_voltarget.py` (before the `if __name__` block):

```python
class TestEvaluatePaired(unittest.TestCase):
    def _stream(self):
        # (entry_index, R, atr_frac) — 6 trades across bars 0..5, all tradeable
        return [(0, 1.0, 0.02), (1, -0.5, 0.02), (2, 1.0, 0.01),
                (3, -0.5, 0.01), (4, 1.0, 0.02), (5, -0.5, 0.02)]

    def test_returns_both_arms_and_stage_metrics(self):
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        for k in ("screen_trades", "screen_expectancy_r", "holdout_trades",
                  "holdout_control_mar", "holdout_treatment_mar",
                  "holdout_treatment_dd", "holdout_dominance",
                  "research_sharpe", "research_skew", "research_kurtosis",
                  "research_trades", "research_control_mar",
                  "research_treatment_mar", "target_risk"):
            self.assertIn(k, m)

    def test_screen_expectancy_is_sizing_independent(self):
        # expectancy-R is computed from raw R, identical to summarize_r
        import statistics
        screen_rs = [1.0, -0.5, 1.0, -0.5]
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        self.assertAlmostEqual(m["screen_expectancy_r"],
                               statistics.fmean(screen_rs))

    def test_iso_calibration_uses_screen_only(self):
        # target_risk calibrated on screen trades (entry_index < split)
        m = voltarget.evaluate_paired(self._stream(), split_index=4)
        screen_afs = [0.02, 0.02, 0.01, 0.01]
        expected_tr = voltarget.calibrate_target_risk(screen_afs)
        self.assertAlmostEqual(m["target_risk"], round(expected_tr, 8))


class TestStageGates(unittest.TestCase):
    def test_stage1_needs_trades_and_positive_expectancy(self):
        self.assertTrue(voltarget.stage1_paired(
            {"screen_trades": 30, "screen_expectancy_r": 0.1}))
        self.assertFalse(voltarget.stage1_paired(
            {"screen_trades": 29, "screen_expectancy_r": 0.1}))
        self.assertFalse(voltarget.stage1_paired(
            {"screen_trades": 30, "screen_expectancy_r": 0.0}))

    def test_stage2_requires_positive_mar_budget_and_dominance(self):
        ok = {"holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
              "holdout_dominance": True}
        self.assertTrue(voltarget.stage2_paired(ok))
        # budget breach
        bad_dd = {**ok, "holdout_treatment_dd": -0.40}
        self.assertFalse(voltarget.stage2_paired(bad_dd))
        # no dominance
        no_dom = {**ok, "holdout_dominance": False}
        self.assertFalse(voltarget.stage2_paired(no_dom))

    def test_stage4_lockbox_gate(self):
        ok = {"tail_treatment_mar": 1.0, "tail_treatment_dd": -0.2,
              "tail_trades": 10, "tail_dominance": True}
        self.assertTrue(voltarget.stage4_paired(ok))
        self.assertFalse(voltarget.stage4_paired({**ok, "tail_treatment_mar": 0.9}))
        self.assertFalse(voltarget.stage4_paired({**ok, "tail_trades": 9}))


class TestPairedResearchAndLockbox(unittest.TestCase):
    def setUp(self):
        from moonface.foundation.bundle import DataBundle
        from moonface.research.synth import make_candles
        # Flat funding => sd==0 => no funding_fade entries => empty stream.
        # Shape/determinism only (network-free, no trade count asserted).
        self.candles = make_candles(400, seed=7)
        self.bundle = DataBundle(candles=self.candles, funding=[0.0] * 400)
        from moonface.research.spec import HypothesisSpec
        fam, ep = voltarget.VOLTARGET_ENTRY
        name, xp = voltarget.VOLTARGET_EXIT
        self.spec = HypothesisSpec(
            domain="funding_fade_voltarget", version=1,
            asset={"exchange": "binance", "symbol": "ETH/USDT:USDT",
                   "timeframe": "4h", "funding_symbol": "ETH/USDT:USDT"},
            entry={"family": fam, "params": ep},
            exit={"name": name, "params": xp}, fraction=voltarget.CONTROL_FRACTION)

    def test_research_shape_and_deterministic(self):
        m = voltarget.paired_research(self.spec, self.bundle)
        self.assertEqual(m["research_trades"], 0)   # flat funding -> no entries
        self.assertEqual(m["screen_trades"], 0)
        self.assertEqual(voltarget.paired_research(self.spec, self.bundle), m)

    def test_lockbox_tail_is_post_fence(self):
        fence_index = 320  # 80% of 400
        m = voltarget.paired_lockbox(self.spec, self.bundle, fence_index)
        self.assertEqual(m["tail_trades"], 0)       # flat funding -> no entries
        self.assertIn("tail_treatment_mar", m)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voltarget.py -v`
Expected: FAIL — `AttributeError: module 'moonface.research.voltarget' has no attribute 'evaluate_paired'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/moonface/research/voltarget.py`:

```python
def evaluate_paired(stream: list[tuple[int, float, float]], split_index: int,
                    control_fraction: float = CONTROL_FRACTION) -> dict:
    """One pass over a research-window stream split at bar index `split_index`.
    target_risk is calibrated on screen trades (no lookahead) and applied
    unchanged to holdout and full. Returns both arms + stage metrics + paired
    dominance on the holdout."""
    screen = [(r, af) for i, r, af in stream if i < split_index]
    holdout = [(r, af) for i, r, af in stream if i >= split_index]
    full = [(r, af) for _, r, af in stream]
    screen_summary = summarize_r([r for r, _ in screen])

    target_risk = calibrate_target_risk([af for _, af in screen]) if screen else 0.0
    ctrl_hold = equity_summary(holdout, control_fraction)
    trt_hold = equity_summary_from_returns(treatment_returns(holdout, target_risk))
    ctrl_full = equity_summary(full, control_fraction)
    trt_full = equity_summary_from_returns(treatment_returns(full, target_risk))
    return {
        "screen_trades": screen_summary.trade_count,
        "screen_expectancy_r": screen_summary.expectancy_r,
        "holdout_trades": ctrl_hold.trade_count,
        "holdout_control_mar": ctrl_hold.mar,
        "holdout_treatment_mar": trt_hold.mar,
        "holdout_treatment_dd": trt_hold.max_drawdown,
        "holdout_dominance": paired_dominance(trt_hold, ctrl_hold),
        "research_sharpe": trt_full.sharpe,
        "research_skew": trt_full.skew,
        "research_kurtosis": trt_full.kurtosis,
        "research_trades": trt_full.trade_count,
        "research_control_mar": ctrl_full.mar,
        "research_treatment_mar": trt_full.mar,
        "target_risk": round(target_risk, 8),
    }


def stage1_paired(m: dict) -> bool:
    return m["screen_trades"] >= SCREEN_MIN_TRADES and m["screen_expectancy_r"] > 0.0


def stage2_paired(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def paired_research(spec, research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    stream = r_stream(spec, research)
    split = int(len(research.candles) * screen_fraction)
    return evaluate_paired(stream, split)


def paired_lockbox(spec, full, fence_index: int,
                   screen_fraction: float = SCREEN_FRACTION) -> dict:
    """Tail (entry_index >= fence_index) for both arms. target_risk calibrated on
    the screen window of the research region (bars < screen_fraction*fence) —
    identical to paired_research's calibration, so no tail lookahead."""
    stream = r_stream(spec, full)
    screen_split = int(fence_index * screen_fraction)
    screen_afs = [af for i, r, af in stream if i < screen_split]
    target_risk = calibrate_target_risk(screen_afs) if screen_afs else 0.0
    tail = [(r, af) for i, r, af in stream if i >= fence_index]
    ctrl = equity_summary(tail, CONTROL_FRACTION)
    trt = equity_summary_from_returns(treatment_returns(tail, target_risk))
    return {
        "tail_trades": trt.trade_count,
        "tail_control_mar": ctrl.mar,
        "tail_treatment_mar": trt.mar,
        "tail_treatment_dd": trt.max_drawdown,
        "tail_dominance": paired_dominance(trt, ctrl),
        "target_risk": round(target_risk, 8),
    }


def stage4_paired(m: dict) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= LOCKBOX_MIN_TRADES
            and m["tail_dominance"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voltarget.py -v`
Expected: PASS (all classes green).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/voltarget.py tests/test_voltarget.py
git commit -m "feat(research): paired research/lockbox evaluators + stage gates"
```

---

### Task 3: rolling walk-forward (stage 3.5)

**Files:**
- Create: `src/moonface/research/voltarget_wf.py`
- Test: `tests/test_voltarget_wf.py`

**Interfaces:**
- Consumes: `moonface.foundation.bundle.DataBundle`; `moonface.foundation.metrics` (`equity_summary_from_returns`, `MAX_LEVERAGE`); `moonface.research.ladder.r_stream`; Task 1 (`CONTROL_FRACTION`, `calibrate_target_risk`, `treatment_returns`, `paired_dominance`).
- Produces: `walk_forward_paired(spec, research, train_bars=TRAIN_BARS, test_bars=TEST_BARS, step_bars=STEP_BARS) -> dict`; `stage35_paired(wf) -> bool`; constants `TRAIN_BARS`, `TEST_BARS`, `STEP_BARS`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_voltarget_wf.py`:

```python
# tests/test_voltarget_wf.py
import unittest

from moonface.foundation.bundle import DataBundle
from moonface.research import voltarget_wf
from moonface.research.spec import HypothesisSpec
from moonface.research.synth import make_candles


def _spec():
    fam, ep = voltarget_wf.VOLTARGET_ENTRY
    name, xp = voltarget_wf.VOLTARGET_EXIT
    return HypothesisSpec(
        domain="funding_fade_voltarget", version=1,
        asset={"exchange": "binance", "symbol": "ETH/USDT:USDT",
               "timeframe": "4h", "funding_symbol": "ETH/USDT:USDT"},
        entry={"family": fam, "params": ep},
        exit={"name": name, "params": xp}, fraction=0.01)


class TestWalkForwardGeometry(unittest.TestCase):
    def test_fold_count_from_geometry(self):
        # n=12000 bars, train=6570, test=step=1095 -> folds where start+1095<=12000
        bundle = DataBundle(candles=make_candles(12000, seed=3),
                            funding=[0.0] * 12000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        expected = len(range(6570, 12000 - 1095 + 1, 1095))
        self.assertEqual(wf["folds"], expected)
        self.assertGreaterEqual(expected, 4)

    def test_returns_both_arms_and_dominance(self):
        bundle = DataBundle(candles=make_candles(12000, seed=3),
                            funding=[0.0] * 12000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        for k in ("folds", "aggregate_control_mar", "aggregate_treatment_mar",
                  "aggregate_treatment_sharpe", "aggregate_trades", "dominance"):
            self.assertIn(k, wf)

    def test_too_short_window_yields_no_folds(self):
        bundle = DataBundle(candles=make_candles(1000, seed=3),
                            funding=[0.0] * 1000)
        wf = voltarget_wf.walk_forward_paired(_spec(), bundle)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(voltarget_wf.stage35_paired(wf))


class TestStage35Gate(unittest.TestCase):
    def test_passes_on_positive_mar_and_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_trades": 40,
              "dominance": True}
        self.assertTrue(voltarget_wf.stage35_paired(ok))

    def test_fails_without_dominance(self):
        ok = {"folds": 4, "aggregate_treatment_mar": 0.5,
              "aggregate_treatment_sharpe": 0.2, "aggregate_trades": 40,
              "dominance": False}
        self.assertFalse(voltarget_wf.stage35_paired(ok))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voltarget_wf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.voltarget_wf'`

- [ ] **Step 3: Write minimal implementation**

Create `src/moonface/research/voltarget_wf.py`:

```python
# src/moonface/research/voltarget_wf.py
"""Rolling walk-forward for funding_fade + fixed_bracket (spec §6.4, stage 3.5).

Train strictly precedes test; target_risk is calibrated in each fold's TRAIN
window only (no lookahead); control uses constant CONTROL_FRACTION. Aggregates
pooled TEST-window returns for both arms. Adapts research/walkforward.py's
geometry to the r_stream primitive with NO param selection (frozen construction)."""
from __future__ import annotations

from moonface.foundation.bundle import DataBundle
from moonface.foundation.metrics import MAX_LEVERAGE, equity_summary_from_returns
from moonface.research.ladder import r_stream
from moonface.research.voltarget import (CONTROL_FRACTION, VOLTARGET_ENTRY,
                                         VOLTARGET_EXIT, calibrate_target_risk,
                                         paired_dominance, treatment_returns)

_BARS_PER_DAY = 6                          # 4h bars
TRAIN_BARS = 3 * 365 * _BARS_PER_DAY       # 3-year train  (= 6570)
TEST_BARS = int(0.5 * 365 * _BARS_PER_DAY)  # 6-month test  (= 1095)
STEP_BARS = TEST_BARS                       # non-overlapping 6-month steps


def _sub_bundle(bundle: DataBundle, lo: int, hi: int) -> DataBundle:
    def cut(seq):
        return seq[lo:hi] if seq is not None else None
    return DataBundle(candles=bundle.candles[lo:hi], funding=cut(bundle.funding),
                      basis=cut(bundle.basis), feature=cut(bundle.feature))


def walk_forward_paired(spec, research: DataBundle, train_bars: int = TRAIN_BARS,
                        test_bars: int = TEST_BARS,
                        step_bars: int = STEP_BARS) -> dict:
    n = len(research.candles)
    ctrl_returns: list[float] = []
    trt_returns: list[float] = []
    folds = 0
    start = train_bars
    while start + test_bars <= n:
        train = _sub_bundle(research, start - train_bars, start)
        test = _sub_bundle(research, start, start + test_bars)
        train_afs = [af for _, _, af in r_stream(spec, train)]
        target_risk = calibrate_target_risk(train_afs) if train_afs else 0.0
        test_trades = [(r, af) for _, r, af in r_stream(spec, test)]
        for r, af in test_trades:
            ctrl_returns.append(min(CONTROL_FRACTION, MAX_LEVERAGE * af) * r)
        trt_returns.extend(treatment_returns(test_trades, target_risk))
        folds += 1
        start += step_bars
    ctrl = equity_summary_from_returns(ctrl_returns)
    trt = equity_summary_from_returns(trt_returns)
    return {
        "folds": folds,
        "aggregate_control_mar": ctrl.mar,
        "aggregate_treatment_mar": trt.mar,
        "aggregate_treatment_sharpe": trt.sharpe,
        "aggregate_trades": trt.trade_count,
        "dominance": paired_dominance(trt, ctrl),
    }


def stage35_paired(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voltarget_wf.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/voltarget_wf.py tests/test_voltarget_wf.py
git commit -m "feat(research): rolling walk-forward stage 3.5 for vol-target program"
```

---

### Task 4: domain runner (orchestration + verdict)

**Files:**
- Create: `src/moonface/research/voltarget_runner.py`
- Test: `tests/test_voltarget_runner.py`

**Interfaces:**
- Consumes: `Store` (`register_domain`, `insert_grid`, `domain`, `rows`, `touch_lockbox`, `set_domain_status`); `FencedBundle`; `spec_from_json`, `spec_hash`; `deflated_sharpe`; Tasks 1–3 (`paired_research`, `paired_lockbox`, `stage1_paired`, `stage2_paired`, `stage4_paired`, `walk_forward_paired`, `stage35_paired`, `voltarget_specs`); `DSR_THRESHOLD`, `SCREEN_FRACTION`.
- Produces: `VOLTARGET_DOMAIN`, `VOLTARGET_ASSETS`, `voltarget_specs()`, `register(store, now_ms)`, `run_domain(store, loader, out_root) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voltarget_runner.py`:

```python
# tests/test_voltarget_runner.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from moonface.foundation.bundle import DataBundle
from moonface.research import voltarget_runner as vr
from moonface.research.spec import spec_hash
from moonface.research.store import Store
from moonface.research.synth import make_candles


def _flat_bundle(asset, start_ms, end_ms):
    """Loader stub: flat funding -> no funding_fade entries -> stage 1 fails."""
    candles = make_candles(6000, seed=11)
    return DataBundle(candles=candles, funding=[0.0] * len(candles))


class TestRegister(unittest.TestCase):
    def test_register_creates_domain_with_bespoke_runner_config(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertIsNotNone(d)
            self.assertEqual(d["config"].get("runner"), "voltarget")
            self.assertEqual(d["grid_size"], 2)         # ETH + SOL
            self.assertFalse(d["lockbox_touched"])

    def test_register_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            vr.register(store, now_ms=1_800_000_000_000)  # must not overwrite
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertEqual(d["end_ms"], 1_700_000_000_000)


class TestRunDomainNegativePath(unittest.TestCase):
    def test_flat_funding_closes_negative_without_spending_lockbox(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            verdict = vr.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_negative")
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertFalse(d["lockbox_touched"])      # never earned the tail
            self.assertEqual(d["status"], "closed_negative")
            self.assertTrue((Path(td) / vr.VOLTARGET_DOMAIN / "verdict.md").exists())


class TestRunDomainPositivePath(unittest.TestCase):
    def _stub(self):
        """Force every stage to pass so we exercise lockbox spend + promotion."""
        research_m = {"screen_trades": 40, "screen_expectancy_r": 0.2,
                      "holdout_treatment_mar": 0.5, "holdout_treatment_dd": -0.1,
                      "holdout_dominance": True, "research_sharpe": 0.3,
                      "research_skew": 0.0, "research_kurtosis": 3.0,
                      "research_trades": 80, "research_control_mar": 0.1,
                      "research_treatment_mar": 0.5, "target_risk": 1e-05}
        wf_m = {"folds": 4, "aggregate_control_mar": 0.1,
                "aggregate_treatment_mar": 0.5, "aggregate_treatment_sharpe": 0.4,
                "aggregate_trades": 40, "dominance": True}
        tail_m = {"tail_trades": 20, "tail_control_mar": 0.5,
                  "tail_treatment_mar": 1.2, "tail_treatment_dd": -0.2,
                  "tail_dominance": True, "target_risk": 1e-05}
        return research_m, wf_m, tail_m

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            vr.register(store, now_ms=1_700_000_000_000)
            research_m, wf_m, tail_m = self._stub()
            with mock.patch.object(vr, "paired_research", return_value=research_m), \
                 mock.patch.object(vr, "walk_forward_paired", return_value=wf_m), \
                 mock.patch.object(vr, "paired_lockbox", return_value=tail_m):
                verdict = vr.run_domain(store, _flat_bundle, Path(td))
            self.assertEqual(verdict, "closed_positive")
            d = store.domain(vr.VOLTARGET_DOMAIN, 1)
            self.assertTrue(d["lockbox_touched"])       # spent exactly once


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voltarget_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.voltarget_runner'`

- [ ] **Step 3: Write minimal implementation**

Create `src/moonface/research/voltarget_runner.py`:

```python
# src/moonface/research/voltarget_runner.py
"""Dedicated runner for the funding_fade_voltarget domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) and FencedBundle (one-touch
tail), but drives the paired vol-targeted ladder + walk-forward itself — the
generic runner.run cannot express per-trade vol-targeted sizing. The generic
runner skips any domain whose config.runner is neither None nor 'generic'
(see the guard added to runner.run)."""
from __future__ import annotations

import json
from pathlib import Path

from moonface.foundation.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.research.lockbox import FencedBundle
from moonface.research.spec import HypothesisSpec, spec_from_json, spec_hash
from moonface.research.store import Store
from moonface.research.voltarget import (CONTROL_FRACTION, VOLTARGET_ENTRY,
                                         VOLTARGET_EXIT, paired_lockbox,
                                         paired_research, stage1_paired,
                                         stage2_paired, stage4_paired)
from moonface.research.voltarget_wf import stage35_paired, walk_forward_paired

VOLTARGET_DOMAIN = "funding_fade_voltarget"
VOLTARGET_START_MS = 1_577_836_800_000   # 2020-01-01 UTC
LOCKBOX_FRACTION = 0.2
VOLTARGET_ASSETS = [
    {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "ETH/USDT:USDT"},
    {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "SOL/USDT:USDT"},
]


def voltarget_specs() -> list[HypothesisSpec]:
    fam, ep = VOLTARGET_ENTRY
    name, xp = VOLTARGET_EXIT
    return [HypothesisSpec(domain=VOLTARGET_DOMAIN, version=1, asset=a,
                           entry={"family": fam, "params": ep},
                           exit={"name": name, "params": xp},
                           fraction=CONTROL_FRACTION)
            for a in VOLTARGET_ASSETS]


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 2-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - VOLTARGET_START_MS) * LOCKBOX_FRACTION)
    if store.domain(VOLTARGET_DOMAIN, 1) is None:
        store.register_domain(VOLTARGET_DOMAIN, 1, "active",
                              {"runner": "voltarget", "assets": VOLTARGET_ASSETS},
                              VOLTARGET_START_MS, now_ms, fence_ts)
        store.insert_grid(VOLTARGET_DOMAIN, 1, voltarget_specs())


def _dsr(passing: list[dict], all_sharpes: list[float], grid_size: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in passing:
        out[r["spec_hash"]] = deflated_sharpe(
            r["research_sharpe"], r["research_trades"], r["research_skew"],
            r["research_kurtosis"], all_sharpes, grid_size)
    return out


def run_domain(store: Store, loader, out_root: Path) -> str:
    d = store.domain(VOLTARGET_DOMAIN, 1)
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(VOLTARGET_DOMAIN, 1)]
    grid_size = len(specs)
    fenced: dict[str, FencedBundle] = {}

    def fb_for(spec):
        key = json.dumps(spec.asset, sort_keys=True)
        if key not in fenced:
            fenced[key] = FencedBundle(loader(spec.asset, d["start_ms"], d["end_ms"]),
                                       d["fence_ts"])
        return fenced[key]

    # Pass 1: stages 1, 2, 3.5 per spec; collect research metrics for ALL specs
    # (DSR trial variance uses every spec's research Sharpe, per ladder.stage3_dsr).
    rows: list[dict] = []
    for spec in specs:
        h = spec_hash(spec)
        fb = fb_for(spec)
        research = fb.research()
        m = paired_research(spec, research, SCREEN_FRACTION)
        rows.append({"spec_hash": h, "spec": spec, "m": m, "wf": None,
                     "stage": "research"})
        if not stage1_paired(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_paired(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward_paired(spec, research)
        rows[-1]["wf"] = wf
        if not stage35_paired(wf):
            rows[-1]["stage"] = "rejected_wf"
            continue
        rows[-1]["stage"] = "wf_pass"

    # Pass 2: DSR (stage 3) across all specs that passed 1/2/3.5.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    wf_passers = [r for r in rows if r["stage"] == "wf_pass"]
    dsr = _dsr(wf_passers, all_sharpes, grid_size) if wf_passers else {}
    for r in wf_passers:
        r["dsr"] = dsr.get(r["spec_hash"], 0.0)
        if r["dsr"] < DSR_THRESHOLD:
            r["stage"] = "rejected_dsr"

    # Pass 3: one-touch lockbox (stage 4) only if EVERY spec survived 1..3.5+DSR.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if grid_size > 0 and len(survivors) == grid_size:
        store.touch_lockbox(VOLTARGET_DOMAIN, 1)
        for r in survivors:
            fb = fb_for(r["spec"])
            tail = paired_lockbox(r["spec"], fb.full, fb.fence_index, SCREEN_FRACTION)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_paired(tail) else "lockbox_fail"

    promoted = (grid_size > 0
                and all(r["stage"] == "lockbox_pass" for r in rows))
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(VOLTARGET_DOMAIN, 1, verdict)
    _write_verdict(out_root, verdict, rows, dsr)
    return verdict


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float]) -> None:
    lines = [
        "# funding_fade_voltarget v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {VOLTARGET_DOMAIN} (vol/risk-targeted sizing vs fixed-fractional)",
        f"- **Construction:** funding_fade {VOLTARGET_ENTRY[1]} + {VOLTARGET_EXIT[0]}"
        f" {VOLTARGET_EXIT[1]}",
        "- **Promotion requires BOTH assets to clear stages 1-4 and dominate the"
        " control on MAR & Sharpe at holdout, WF aggregate, and lockbox tail.",
        "",
        "| asset | final stage | screen n | holdout trt MAR | WF folds | DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        symbol = r["spec"].asset["symbol"]
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = f"{r['tail']['tail_treatment_mar']:.3f}" if r.get("tail") else "-"
        lines.append(f"| {symbol} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | {dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2, no fraction"
              " grid, no budget relaxation. The vol/risk-targeting lever is terminal"
              " for funding_fade + fixed_bracket on a closed-negative verdict."]
    d = out_root / VOLTARGET_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voltarget_runner.py -v`
Expected: PASS (register idempotent; negative path closes negative with pristine lockbox; positive path spends lockbox once and promotes).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/voltarget_runner.py tests/test_voltarget_runner.py
git commit -m "feat(research): voltarget domain runner with paired ladder + one-touch lockbox"
```

---

### Task 5: generic-runner guard + CLI subcommand

**Files:**
- Modify: `src/moonface/research/runner.py` (add bespoke-runner skip)
- Modify: `tools/research.py` (add `voltarget` subcommand)
- Modify: `tests/test_research_runner.py` (guard test)

**Interfaces:**
- Consumes: `voltarget_runner.register`, `voltarget_runner.run_domain`; existing `runner.run`, `Store`, `load_bundle`.
- Produces: `cmd_voltarget(args)`; a `voltarget` subparser; the guard in `runner.run`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_research_runner.py`:

```python
class TestBespokeRunnerGuard(unittest.TestCase):
    def test_generic_run_skips_bespoke_runner_domain(self):
        import tempfile
        from moonface.research.runner import run
        from moonface.research.store import Store

        with tempfile.TemporaryDirectory() as td:
            store = Store(td + "/s.db")
            store.register_domain("funding_fade_voltarget", 1, "active",
                                  {"runner": "voltarget"}, 1, 2, 2)
            store.insert_grid("funding_fade_voltarget", 1, [])  # grid_size 0 is fine here
            # A loader that would explode if called proves the domain was skipped.
            def loader(asset, start_ms, end_ms):
                raise AssertionError("generic runner must not load bespoke domains")
            b = run(store, loader, out_root=Path(td))
            self.assertEqual(b.kind, "idle")
```

If `tests/test_research_runner.py` does not already import `Path`, add `from pathlib import Path` to its imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_research_runner.py::TestBespokeRunnerGuard -v`
Expected: FAIL — `AssertionError: generic runner must not load bespoke domains` (the generic runner currently processes the active bespoke domain).

- [ ] **Step 3: Add the guard to `runner.run`**

In `src/moonface/research/runner.py`, inside the `for d in store.domains_in_order():` loop, immediately after the `if only_domain ...` block (and before the `if d["status"] in (...)` skip), insert:

```python
        if d["config"].get("runner") not in (None, "generic"):
            continue  # bespoke-runner domains (e.g. funding_fade_voltarget) have their own driver
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_research_runner.py::TestBespokeRunnerGuard -v`
Expected: PASS.

- [ ] **Step 5: Add the `voltarget` CLI subcommand**

In `tools/research.py`:

Add to the imports (after the `funding_fade_ref` import block, lines ~12-19):

```python
from moonface.research.voltarget_runner import (VOLTARGET_DOMAIN,
                                                register as register_voltarget,
                                                run_domain as run_voltarget)
import time as _time
```

Add the handler near `cmd_funding_ref` (after line 120):

```python
def cmd_voltarget(args: argparse.Namespace) -> None:
    """Register + run the funding_fade_voltarget domain and print the verdict.
    Drives its own paired ladder + walk-forward + one-touch lockbox."""
    store = _store(args)
    now_ms = int(_time.time() * 1000)
    register_voltarget(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_voltarget(store, loader, Path(args.out_root))
    print(f"{VOLTARGET_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / VOLTARGET_DOMAIN / 'verdict.md'}")
```

Register the subparser in `build_parser` (after the `funding-ref` subparser block, before `return p`):

```python
    vt = sub.add_parser("voltarget",
                        help="register + run funding_fade_voltarget (paired"
                             " vol-targeted vs fixed-fractional, ETH/SOL)")
    vt.add_argument("--cache-dir", default=".backtest_cache")
    vt.set_defaults(fn=cmd_voltarget)
```

- [ ] **Step 6: Verify the CLI wires up**

Run: `python tools/research.py voltarget --help`
Expected: prints usage with `--cache-dir` and the help string; exits 0.

Run: `pytest tests/test_research_runner.py tests/test_voltarget.py tests/test_voltarget_wf.py tests/test_voltarget_runner.py -v`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add src/moonface/research/runner.py tools/research.py tests/test_research_runner.py
git commit -m "feat(research): generic-runner bespoke guard + voltarget CLI subcommand"
```

---

### Task 6: pre-registration artifact + full verification

**Files:**
- Create: `experiments/funding_fade_voltarget/PREREGISTRATION.md`

**Interfaces:**
- Consumes: the committed spec + all code from Tasks 1–5.

- [ ] **Step 1: Write the pre-registration artifact**

Create `experiments/funding_fade_voltarget/PREREGISTRATION.md`:

```markdown
# funding_fade_voltarget v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Lineage: successor to `funding_fade_transfer` (closed
negative 2026-06-15) and the profit-maximization program; the single new lever
is per-trade vol/risk targeting. Design spec:
`docs/research-log/specs/2026-07-02-funding-fade-voltarget-design.md`.

## 1. Hypothesis
`funding_fade{window:60,z_thr:1.5}` + `fixed_bracket{k_stop:2.0,m_tp:4.0,atr_period:14}`,
sized by vol/risk targeting (constant stop-risk, iso-average-risk), earns
positive OOS risk-adjusted return on ETH and SOL AND beats the fixed-fractional
baseline on both MAR and Sharpe.

## 2. Treatment vs control (the one variable)
- Control: fixed-fractional `f = 0.01`.
- Treatment: `f_i = clamp(target_risk / atr_frac_i, 0, 5.0 * atr_frac_i)`, with
  `target_risk` calibrated so `mean(f_i over screen) = 0.01`. Same entries,
  exits, and splits — only the sizing rule differs.

## 3. Evaluation (hybrid)
Standard ladder (screen 70% / holdout, DSR ≥ 0.95, one-touch lockbox tail MAR
≥ 1.0 / DD ≥ −0.30 / ≥ 10 trades) + rolling walk-forward (3 yr train / 6 mo
test / 6 mo step, per-fold calibration). The treatment must clear every stage
AND strictly dominate the control on MAR & Sharpe at holdout, WF aggregate,
and lockbox tail.

## 4. Decision
- → PAPER-LIVE WATCHING iff BOTH ETH and SOL clear all stages and dominate.
- → CLOSED NEGATIVE otherwise. Kill rule: no v2, no fraction grid, no budget
  relaxation. n_trials = 2.

## 5. Run
`python tools/research.py voltarget`
```

- [ ] **Step 2: Run the full test suite**

Run: `pytest -q`
Expected: PASS — all existing tests plus the new `test_voltarget*.py` and the guard test green.

- [ ] **Step 3: Smoke-run the program end-to-end (optional, network-free)**

If `.backtest_cache/` has ETH/SOL 4h + funding data, run:
`python tools/research.py voltarget`
Expected: prints `funding_fade_voltarget v1: closed_positive|closed_negative` and writes `experiments/research/funding_fade_voltarget/verdict.md`. (If the cache is absent, this step is skipped — the verdict is produced once data is available; the program logic is fully covered by the unit tests.)

- [ ] **Step 4: Commit**

```bash
git add -f experiments/funding_fade_voltarget/PREREGISTRATION.md
git commit -m "docs(research): funding_fade_voltarget pre-registration artifact"
```

---

## Notes for the implementer

- **No new dependencies.** Everything uses stdlib + existing MoonFace modules.
- **`r_stream` is the shared primitive** for both arms — never recompute entries/exits; always go through `ladder.r_stream(spec, bundle)`.
- **The treatment compounds via `equity_summary_from_returns`** (per-trade returns); the control via `equity_summary(trades, fraction)`. Do not add a `sizer` field to `HypothesisSpec` — that would touch the frozen spec/store and every other domain.
- **Lockbox discipline:** `touch_lockbox` is called at most once, and only after stages 1–3.5 clear for *every* spec. The `FencedBundle` guarantees research stages cannot see tail candles.
- **DSR trial variance** uses every spec's research Sharpe (including rejected ones), with `grid_size = 2` — mirror `ladder.stage3_dsr`.
- **Determinism:** all synthetic fixtures use `make_candles(seed=...)`; no `datetime.now()`/`random()` in library code.
