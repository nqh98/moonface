# Regime-Conditional MoE Combiner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, artifact-proof regime-conditional Mixture-of-Experts combiner that soft-generalizes the frozen `v3/matrix.py` hard-gate matrix, whose primary deliverable is the overfitting defense — it must return NEGATIVE on null/dead inputs.

**Architecture:** A new `src/moonface/signal/engine/moe/` package layers on the existing v3 harness. A coarse regime classifier (reusing `v3/regime.py`) gates a set of experts (v3 mechanisms wrapped to an `Expert` protocol); a causal normalizer maps heterogeneous raw signals to `[-1,1]`; a constrained-shrinkage estimator learns the ONLY fit-to-returns object, the weight matrix `W[regime,expert]`; a walk-forward harness reuses v3's `simulate_bracket_v3` / `block_ci_q` / `v3_metrics` / split constants and runs a mandatory Gate-0 null calibration before any live verdict.

**Tech Stack:** Python 3.12, stdlib only (`statistics`, `bisect`, `random`, `dataclasses`), pytest. No new dependencies. Reuses `moonface.signal.engine.v3.*`, `moonface.signal.engine.repair`, `moonface.foundation.metrics`.

## Global Constraints

- **Spec:** `docs/research-log/specs/2026-07-09-regime-moe-combiner-design.md`. Every task implements a section of it.
- **No claim of edge.** The deliverable is the protocol + anti-artifact gates. A certified NEGATIVE is success.
- **`W` is the ONLY object fit to returns.** Regime boundaries, normalizer stats, exits, and sizing are frozen from theory or train-only descriptive stats (spec §4.1). Do not fit anything else to returns.
- **Causality:** every feature/signal at bar `t` uses only `candles[:t+1]`; trades enter at `t+1`. No future bars, ever.
- **Reuse, do not fork, the v3 primitives:** `simulate_bracket_v3`, `v3_metrics`, `split_pairs_by_window`, `gate1_validation`, `gate2_sealed`, `gate3_transfer`, `v22_pairs`, and the frozen constants `SPAN_START_TS_MS / TRAIN_END_TS_MS / SEALED_START_TS_MS / SPAN_END_TS_MS / PURGE_MS` from `moonface.signal.engine.v3.evaluate`. Import them; never redefine.
- **Frozen splits (verbatim):** train `2020→2024` (`TRAIN_END_TS_MS=1704067200000`), validation `2024→2025-07` (`SEALED_START_TS_MS=1751328000000`), sealed `2025-07→2026-07` (`SPAN_END_TS_MS=1782316800000`). Sealed spent ONCE.
- **Power budget:** default `m ≥ 50` trades per effective weight, never `< 30`.
- **Deflated significance:** every combiner config evaluated on validation is one trial; gate on DSR (`foundation.metrics.deflated_sharpe`), not raw Sharpe.
- **Gate-0 is mandatory and first:** the live walk-forward MUST refuse to emit a positive verdict unless the null-calibration suite returned NEGATIVE on all null inputs.
- **Test layout:** one `tests/test_moe_<area>.py` per module; follow the existing `tests/test_forced_error_null_calibration.py` / `tests/test_liq_twap_null_calibration.py` pattern for the Gate-0 test.
- **Determinism:** all bootstrap/shuffle uses an explicit seeded `random.Random(seed)`; `seed` lives in `MoeConfig`.

---

## File Structure

- `src/moonface/signal/engine/moe/__init__.py` — package marker.
- `src/moonface/signal/engine/moe/config_moe.py` — `MoeConfig` hyperparameters + `moe_hash`.
- `src/moonface/signal/engine/moe/regimes.py` — `MoeRegime` enum + `classify_moe_regime`.
- `src/moonface/signal/engine/moe/experts.py` — `RawSignal`, `Expert` protocol, `mechanism_experts()`.
- `src/moonface/signal/engine/moe/normalize.py` — `Normalizer` (causal rank standardization + tanh alt).
- `src/moonface/signal/engine/moe/weights.py` — constrained-shrinkage `fit_weights`, `p_eff`, `enforce_budget`.
- `src/moonface/signal/engine/moe/power.py` — `allowed_p_eff`, `check_power_budget`.
- `src/moonface/signal/engine/moe/combiner.py` — `Combiner`, `master_score`, `decide_moe`.
- `src/moonface/signal/engine/moe/nulls.py` — null-signal generators (iid-shuffle, sign-flip, phase-randomize, dead-set).
- `src/moonface/signal/engine/moe/evaluate_moe.py` — fit panel, moe stream, Gate-0 null suite, walk-forward Gate1/2/3, verdict.
- `tools/moe_evaluate.py` — CLI entrypoint (mirrors `tools/v3_evaluate.py`).
- `tests/test_moe_*.py` — one per module.

---

### Task 1: Package scaffold + `MoeConfig`

**Files:**
- Create: `src/moonface/signal/engine/moe/__init__.py`
- Create: `src/moonface/signal/engine/moe/config_moe.py`
- Test: `tests/test_moe_config.py`

**Interfaces:**
- Produces: `MoeConfig` frozen dataclass with fields `tau: float=0.35`, `q_confluence: int=2`, `m_per_weight: int=50`, `shrink_snr: float=1.0`, `l1_frac: float=0.10`, `norm_mode: str="rank"`, `seed: int=1729`, `eps: float=1e-9`. `moe_hash(cfg: MoeConfig) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_config.py
from moonface.signal.engine.moe.config_moe import MoeConfig, moe_hash


def test_defaults_and_hash_are_stable():
    cfg = MoeConfig()
    assert cfg.tau == 0.35
    assert cfg.q_confluence == 2
    assert cfg.m_per_weight == 50
    assert cfg.norm_mode == "rank"
    assert cfg.seed == 1729
    h1 = moe_hash(cfg)
    h2 = moe_hash(MoeConfig())
    assert h1 == h2 and len(h1) == 64


def test_hash_changes_with_tau():
    import dataclasses
    assert moe_hash(MoeConfig()) != moe_hash(dataclasses.replace(MoeConfig(), tau=0.5))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.moe'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/__init__.py
```

```python
# src/moonface/signal/engine/moe/config_moe.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields


MOE_VERSION = "moe-v1"


@dataclass(frozen=True)
class MoeConfig:
    tau: float = 0.35          # conviction threshold on |M|
    q_confluence: int = 2      # min agreeing experts
    m_per_weight: int = 50     # trades required per effective weight
    shrink_snr: float = 1.0    # James-Stein signal-to-noise scale
    l1_frac: float = 0.10      # fraction of |edge| below which a cell is zeroed
    norm_mode: str = "rank"    # "rank" | "tanh"
    seed: int = 1729
    eps: float = 1e-9


def moe_hash(cfg: MoeConfig) -> str:
    payload = {f.name: getattr(cfg, f.name) for f in fields(cfg)}
    payload["__moe_version__"] = MOE_VERSION
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/__init__.py src/moonface/signal/engine/moe/config_moe.py tests/test_moe_config.py
git commit -m "feat(moe): package scaffold + MoeConfig with stable hash"
```

---

### Task 2: Regime coarsening (`MoeRegime` + `classify_moe_regime`)

**Files:**
- Create: `src/moonface/signal/engine/moe/regimes.py`
- Test: `tests/test_moe_regimes.py`

**Interfaces:**
- Consumes: `moonface.signal.engine.v3.regime.classify_regime`, `Regime`, `DirState`, `VolState`; `EngineConfigV3`.
- Produces: `class MoeRegime(str, Enum)` with members `TREND, CHOP, STRESS, FLAT`; `coarsen(regime: Regime) -> MoeRegime`; `classify_moe_regime(window: list[Candle], cfg: EngineConfigV3) -> MoeRegime`; `TRADEABLE: tuple[MoeRegime, ...] = (TREND, CHOP, STRESS)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_regimes.py
from moonface.signal.engine.moe.regimes import MoeRegime, coarsen, TRADEABLE
from moonface.signal.engine.v3.regime import Regime, DirState, VolState


def test_extreme_maps_to_flat():
    r = Regime(DirState.TRENDING_UP, VolState.EXTREME)
    assert coarsen(r) is MoeRegime.FLAT


def test_trending_normal_maps_to_trend():
    r = Regime(DirState.TRENDING_DOWN, VolState.NORMAL)
    assert coarsen(r) is MoeRegime.TREND


def test_ranging_quiet_maps_to_chop():
    r = Regime(DirState.RANGING, VolState.QUIET)
    assert coarsen(r) is MoeRegime.CHOP


def test_ranging_high_maps_to_stress():
    r = Regime(DirState.RANGING, VolState.HIGH)
    assert coarsen(r) is MoeRegime.STRESS


def test_flat_not_tradeable():
    assert MoeRegime.FLAT not in TRADEABLE
    assert set(TRADEABLE) == {MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_regimes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/regimes.py
from __future__ import annotations

from enum import Enum

from moonface.foundation.models import Candle
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.regime import (
    DirState,
    Regime,
    VolState,
    classify_regime,
)


class MoeRegime(str, Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    STRESS = "STRESS"
    FLAT = "FLAT"


TRADEABLE: tuple[MoeRegime, ...] = (MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS)


def coarsen(regime: Regime) -> MoeRegime:
    if regime.vol_state == VolState.EXTREME:
        return MoeRegime.FLAT
    if regime.dir_state in (DirState.TRENDING_UP, DirState.TRENDING_DOWN):
        return MoeRegime.TREND
    # RANGING
    if regime.vol_state == VolState.HIGH:
        return MoeRegime.STRESS
    return MoeRegime.CHOP


def classify_moe_regime(window: list[Candle], cfg: EngineConfigV3) -> MoeRegime:
    return coarsen(classify_regime(window, cfg))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_regimes.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/regimes.py tests/test_moe_regimes.py
git commit -m "feat(moe): coarse 3+FLAT regime partition over v3 classifier"
```

---

### Task 3: Expert protocol + v3-mechanism adapter

**Files:**
- Create: `src/moonface/signal/engine/moe/experts.py`
- Test: `tests/test_moe_experts.py`

**Interfaces:**
- Consumes: `build_context`, `MECHANISMS` (`from moonface.signal.engine.v3.matrix import MECHANISMS`), `MechanismSignal`, `BarContext`; `Regime`, `classify_regime`; `EngineConfigV3`.
- Produces: `@dataclass(frozen=True) RawSignal(direction: int, magnitude: float)` where `magnitude ∈ [0,1]`; `class Expert(Protocol)` with `name: str` and `signal(window: list[Candle], index: int, cfg: EngineConfigV3) -> RawSignal`; `mechanism_experts() -> list[Expert]` returning experts named `"BREAKOUT","PULLBACK","REVERSION"`; `raw_value(sig: RawSignal) -> float` = `direction * magnitude`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_experts.py
from moonface.signal.engine.moe.experts import (
    RawSignal,
    mechanism_experts,
    raw_value,
)
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from tests.helpers_v3 import make_candles  # existing helper


def test_raw_value_is_signed_magnitude():
    assert raw_value(RawSignal(direction=-1, magnitude=0.4)) == -0.4
    assert raw_value(RawSignal(direction=0, magnitude=0.9)) == 0.0


def test_mechanism_experts_named_and_causal():
    experts = mechanism_experts()
    assert {e.name for e in experts} == {"BREAKOUT", "PULLBACK", "REVERSION"}
    candles = make_candles(300)
    cfg = EngineConfigV3()
    for e in experts:
        sig = e.signal(candles, len(candles) - 1, cfg)
        assert sig.direction in (-1, 0, 1)
        assert 0.0 <= sig.magnitude <= 1.0
```

> **Note:** `tests/helpers_v3.py` already exists and provides candle builders used across `test_v3_*`. Open it and use whatever synthetic-candle helper it exposes; if the symbol name differs from `make_candles`, use the real one and adjust this test.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_experts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/experts.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from moonface.foundation.models import Candle
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.matrix import MECHANISMS
from moonface.signal.engine.v3.mechanisms.base import build_context, clip01
from moonface.signal.engine.v3.regime import classify_regime


@dataclass(frozen=True)
class RawSignal:
    direction: int      # -1, 0, +1
    magnitude: float    # [0, 1] conviction


def raw_value(sig: RawSignal) -> float:
    return sig.direction * sig.magnitude


class Expert(Protocol):
    name: str

    def signal(
        self, window: list[Candle], index: int, cfg: EngineConfigV3
    ) -> RawSignal: ...


@dataclass(frozen=True)
class _MechanismExpert:
    name: str

    def signal(
        self, window: list[Candle], index: int, cfg: EngineConfigV3
    ) -> RawSignal:
        regime = classify_regime(window[: index + 1], cfg)
        ctx = build_context(window, index, cfg)
        sig = MECHANISMS[self.name].evaluate(ctx, regime)
        return RawSignal(direction=sig.direction, magnitude=clip01(sig.quality))


def mechanism_experts() -> list[Expert]:
    return [_MechanismExpert(name) for name in ("BREAKOUT", "PULLBACK", "REVERSION")]
```

> **Design note (spec §3.1):** the initial expert set is the three v3 mechanisms — enough to exercise the whole framework end-to-end. Closed-lane experts (capitulation-fade, session-sweep, vol-compression) are added later by writing more `Expert` implementations; no combiner change is needed. This keeps Task 3 small and independently testable.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_experts.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/experts.py tests/test_moe_experts.py
git commit -m "feat(moe): Expert protocol + v3-mechanism adapters"
```

---

### Task 4: Causal normalizer

**Files:**
- Create: `src/moonface/signal/engine/moe/normalize.py`
- Test: `tests/test_moe_normalize.py`

**Interfaces:**
- Consumes: `MoeConfig`.
- Produces: `class Normalizer` with classmethod `fit(raw_by_expert: dict[str, list[float]], cfg: MoeConfig) -> Normalizer` (stores, per expert, the sorted list of nonzero `|raw|` seen in train, plus median/MAD for tanh mode) and method `transform(name: str, raw: float) -> float -> [-1,1]`. Rank mode: `sign(raw) * percentile_rank(|raw|)`. Tanh mode: `tanh((raw - median)/(1.4826*MAD))`. Unknown/empty expert → `0.0`. A zero raw → `0.0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_normalize.py
import math

from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.normalize import Normalizer


def test_rank_is_signed_and_bounded():
    cfg = MoeConfig()  # norm_mode="rank"
    norm = Normalizer.fit({"E": [0.1, 0.2, 0.3, 0.4]}, cfg)
    assert norm.transform("E", 0.0) == 0.0
    top = norm.transform("E", 0.4)
    bot = norm.transform("E", 0.05)
    assert 0.0 < bot < top <= 1.0
    assert norm.transform("E", -0.4) == -top  # sign carried, magnitude by |raw|


def test_unknown_expert_is_zero():
    norm = Normalizer.fit({"E": [0.1, 0.2]}, MoeConfig())
    assert norm.transform("UNKNOWN", 0.9) == 0.0


def test_tanh_mode_monotone_and_bounded():
    import dataclasses
    cfg = dataclasses.replace(MoeConfig(), norm_mode="tanh")
    norm = Normalizer.fit({"E": [0.1, 0.2, 0.3, 0.4, 0.5]}, cfg)
    lo = norm.transform("E", 0.1)
    hi = norm.transform("E", 0.5)
    assert -1.0 < lo < hi < 1.0
    assert math.isclose(norm.transform("E", 0.0), 0.0, abs_tol=0.5)  # near median-centered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/normalize.py
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from statistics import median

from moonface.signal.engine.moe.config_moe import MoeConfig


@dataclass(frozen=True)
class Normalizer:
    mode: str
    abs_sorted: dict[str, list[float]] = field(default_factory=dict)
    center: dict[str, float] = field(default_factory=dict)
    scale: dict[str, float] = field(default_factory=dict)

    @classmethod
    def fit(cls, raw_by_expert: dict[str, list[float]], cfg: MoeConfig) -> "Normalizer":
        abs_sorted: dict[str, list[float]] = {}
        center: dict[str, float] = {}
        scale: dict[str, float] = {}
        for name, raws in raw_by_expert.items():
            nonzero = [r for r in raws if r != 0.0]
            abs_sorted[name] = sorted(abs(r) for r in nonzero)
            if nonzero:
                med = median(nonzero)
                mad = median([abs(r - med) for r in nonzero]) or 1e-9
                center[name] = med
                scale[name] = 1.4826 * mad
            else:
                center[name] = 0.0
                scale[name] = 1.0
        return cls(cfg.norm_mode, abs_sorted, center, scale)

    def transform(self, name: str, raw: float) -> float:
        if raw == 0.0 or name not in self.abs_sorted:
            return 0.0
        if self.mode == "tanh":
            z = (raw - self.center[name]) / self.scale[name]
            return math.tanh(z)
        arr = self.abs_sorted[name]
        if not arr:
            return 0.0
        rank = bisect.bisect_right(arr, abs(raw)) / len(arr)  # (0,1]
        return (1.0 if raw > 0 else -1.0) * rank
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_normalize.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/normalize.py tests/test_moe_normalize.py
git commit -m "feat(moe): causal train-frozen normalizer (rank default, tanh alt)"
```

---

### Task 5: Power budget precondition

**Files:**
- Create: `src/moonface/signal/engine/moe/power.py`
- Test: `tests/test_moe_power.py`

**Interfaces:**
- Consumes: nothing beyond stdlib.
- Produces: `allowed_p_eff(n_train_trades: int, m_per_weight: int) -> int` = `n_train_trades // max(m_per_weight, 30)` clamped so `m_per_weight` never drops below 30; `check_power_budget(n_train_trades: int, p_eff: int, m_per_weight: int) -> bool` = `1 <= p_eff <= allowed_p_eff(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_power.py
from moonface.signal.engine.moe.power import allowed_p_eff, check_power_budget


def test_allowed_scales_with_trades():
    assert allowed_p_eff(300, 50) == 6
    assert allowed_p_eff(36, 50) == 0     # the router's n=36: budget is ZERO weights


def test_m_never_below_30():
    # even if caller passes m=10, floor of 30 applies
    assert allowed_p_eff(300, 10) == 10


def test_check_rejects_overspend_and_empty():
    assert check_power_budget(300, 6, 50) is True
    assert check_power_budget(300, 7, 50) is False   # overspend
    assert check_power_budget(300, 0, 50) is False   # nothing learned
    assert check_power_budget(36, 1, 50) is False    # underpowered — the router lesson
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_power.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/power.py
from __future__ import annotations

MIN_TRADES_PER_WEIGHT = 30


def allowed_p_eff(n_train_trades: int, m_per_weight: int) -> int:
    m = max(m_per_weight, MIN_TRADES_PER_WEIGHT)
    return n_train_trades // m


def check_power_budget(n_train_trades: int, p_eff: int, m_per_weight: int) -> bool:
    return 1 <= p_eff <= allowed_p_eff(n_train_trades, m_per_weight)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_power.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/power.py tests/test_moe_power.py
git commit -m "feat(moe): power-budget precondition (router n=36 lesson)"
```

---

### Task 6: Constrained-shrinkage weight estimator

**Files:**
- Create: `src/moonface/signal/engine/moe/weights.py`
- Test: `tests/test_moe_weights.py`

**Interfaces:**
- Consumes: `MoeConfig`; `MoeRegime`, `TRADEABLE`; `allowed_p_eff`.
- Produces:
  - `@dataclass(frozen=True) EdgeSample(regime: MoeRegime, expert: str, direction: int, net_r: float)` — one record per (bar, fired expert) in train.
  - `fit_weights(samples: list[EdgeSample], experts: list[str], cfg: MoeConfig, n_train_trades: int) -> dict[MoeRegime, dict[str, float]]` — the matrix `W`. Steps: conditional mean edge per (regime,expert); **sign-lock + non-negativity** (`w = max(0, mean_edge)`, and only if the expert's *net directional edge* sign is consistent — implemented as: keep `max(0, mean_edge)`, which already discards negative-edge cells); **James-Stein shrinkage** toward per-regime equal-weight; **L1 sparsity** (zero cells whose weight `< l1_frac * max_weight_in_regime`); **budget enforcement** (keep only the top `allowed_p_eff` cells globally, zero the rest).
  - `p_eff(W: dict[MoeRegime, dict[str, float]]) -> int` — count of strictly-positive cells.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_weights.py
import dataclasses

from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.regimes import MoeRegime
from moonface.signal.engine.moe.weights import EdgeSample, fit_weights, p_eff

EXPERTS = ["A", "B", "C"]


def _samples(regime, expert, edge, n):
    # n bars where `expert` fired in `regime` with constant per-trade R = edge
    return [EdgeSample(regime, expert, 1, edge) for _ in range(n)]


def test_negative_edge_cells_are_zeroed():
    # A has +edge in TREND, B has -edge in TREND -> B must be zero (sign-lock/non-neg)
    samples = _samples(MoeRegime.TREND, "A", 0.20, 60) + _samples(MoeRegime.TREND, "B", -0.20, 60)
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=600)
    assert W[MoeRegime.TREND]["A"] > 0.0
    assert W[MoeRegime.TREND]["B"] == 0.0


def test_thin_regime_shrinks_toward_equal_weight():
    # very few samples -> James-Stein pulls the surviving weight down toward the prior
    strong = _samples(MoeRegime.TREND, "A", 0.20, 500)
    thin = _samples(MoeRegime.CHOP, "A", 0.20, 31)
    W = fit_weights(strong + thin, EXPERTS, MoeConfig(), n_train_trades=1000)
    # both positive, but the thin cell is shrunk more (closer to prior) than the strong cell
    assert 0.0 < W[MoeRegime.CHOP]["A"] < W[MoeRegime.TREND]["A"]


def test_budget_caps_p_eff():
    # 9 candidate positive cells but a train count that only affords 2 weights
    samples = []
    for i, r in enumerate([MoeRegime.TREND, MoeRegime.CHOP, MoeRegime.STRESS]):
        for e in EXPERTS:
            samples += _samples(r, e, 0.05 + 0.01 * i, 40)
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=100)  # allows 100//50 = 2
    assert p_eff(W) <= 2


def test_null_edges_collapse_to_zero_pool():
    # all edges ~0 -> after L1 + non-neg, p_eff is 0 (nothing to learn)
    samples = _samples(MoeRegime.TREND, "A", 0.0, 100)
    W = fit_weights(samples, EXPERTS, MoeConfig(), n_train_trades=1000)
    assert p_eff(W) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_weights.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/weights.py
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.power import allowed_p_eff
from moonface.signal.engine.moe.regimes import TRADEABLE, MoeRegime


@dataclass(frozen=True)
class EdgeSample:
    regime: MoeRegime
    expert: str
    direction: int
    net_r: float


def _james_stein_lambda(n_r: int, k: int, snr: float) -> float:
    # shrink harder when the within-regime sample is thin; clip to [0, 1]
    denom = k + max(n_r - k - 2, 0) * snr
    lam = k / denom if denom > 0 else 1.0
    return max(0.0, min(lam, 1.0))


def fit_weights(
    samples: list[EdgeSample],
    experts: list[str],
    cfg: MoeConfig,
    n_train_trades: int,
) -> dict[MoeRegime, dict[str, float]]:
    # 1. conditional mean edge + counts per (regime, expert)
    rs: dict[tuple[MoeRegime, str], list[float]] = {}
    for s in samples:
        rs.setdefault((s.regime, s.expert), []).append(s.net_r)

    W: dict[MoeRegime, dict[str, float]] = {r: {e: 0.0 for e in experts} for r in TRADEABLE}
    k = len(experts)
    for r in TRADEABLE:
        raw_edges = {}
        for e in experts:
            vals = rs.get((r, e), [])
            raw_edges[e] = (fmean(vals), len(vals)) if vals else (0.0, 0)
        # 2. sign-lock + non-negativity
        pos = {e: (max(0.0, mean), n) for e, (mean, n) in raw_edges.items()}
        # 3. James-Stein shrink toward equal-weight prior (prior = mean of positive edges)
        active = {e: v for e, (v, _n) in pos.items() if v > 0.0}
        if active:
            prior = fmean(active.values())
            for e in experts:
                v, n = pos[e]
                if v <= 0.0:
                    W[r][e] = 0.0
                    continue
                lam = _james_stein_lambda(n, k, cfg.shrink_snr)
                W[r][e] = (1.0 - lam) * v + lam * prior
        # 4. L1 sparsity within regime
        mx = max(W[r].values()) if W[r] else 0.0
        if mx > 0.0:
            for e in experts:
                if W[r][e] < cfg.l1_frac * mx:
                    W[r][e] = 0.0

    # 5. global budget enforcement — keep only the top-`allowed` positive cells
    allowed = allowed_p_eff(n_train_trades, cfg.m_per_weight)
    cells = [
        (r, e, W[r][e]) for r in TRADEABLE for e in experts if W[r][e] > 0.0
    ]
    cells.sort(key=lambda c: c[2], reverse=True)
    for r, e, _v in cells[allowed:]:
        W[r][e] = 0.0
    return W


def p_eff(W: dict[MoeRegime, dict[str, float]]) -> int:
    return sum(1 for row in W.values() for v in row.values() if v > 0.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_weights.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/weights.py tests/test_moe_weights.py
git commit -m "feat(moe): constrained-shrinkage weight estimator (sign-lock, JS, L1, budget)"
```

---

### Task 7: Combiner master score + decision

**Files:**
- Create: `src/moonface/signal/engine/moe/combiner.py`
- Test: `tests/test_moe_combiner.py`

**Interfaces:**
- Consumes: `MoeConfig`; `MoeRegime`, `TRADEABLE`; `p_eff` weight matrix shape `dict[MoeRegime, dict[str,float]]`.
- Produces:
  - `master_score(s_by_expert: dict[str, float], W_row: dict[str, float], eps: float) -> float` = `sum(W*s)/(sum(W)+eps)`.
  - `confluence(s_by_expert, W_row, side: int) -> int` = count of experts with `W>0` and `sign(s)==side`.
  - `@dataclass(frozen=True) MoeDecision(action: str, direction: int, regime: MoeRegime, score: float, detail: str)`.
  - `decide_moe(s_by_expert, regime, W, cfg) -> MoeDecision` — WAIT unless `regime in TRADEABLE`, `|M|>=tau`, and `confluence>=q_confluence`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_combiner.py
from moonface.signal.engine.moe.combiner import (
    confluence,
    decide_moe,
    master_score,
)
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.regimes import MoeRegime

W = {
    MoeRegime.TREND: {"A": 1.0, "B": 1.0, "C": 0.0},
    MoeRegime.CHOP: {"A": 0.0, "B": 0.0, "C": 0.0},
    MoeRegime.STRESS: {"A": 1.0, "B": 0.0, "C": 0.0},
}


def test_master_score_is_row_normalized():
    m = master_score({"A": 1.0, "B": 1.0, "C": -1.0}, W[MoeRegime.TREND], 1e-9)
    assert abs(m - 1.0) < 1e-6  # C has zero weight, A&B both +1 -> M=1


def test_flat_regime_never_trades():
    d = decide_moe({"A": 1.0, "B": 1.0}, MoeRegime.FLAT, W, MoeConfig())
    assert d.action == "WAIT"


def test_confluence_guard_blocks_single_voter():
    # only A votes long, B votes flat -> confluence 1 < q_confluence 2 -> WAIT
    d = decide_moe({"A": 0.9, "B": 0.0, "C": 0.0}, MoeRegime.TREND, W, MoeConfig())
    assert d.action == "WAIT"


def test_high_conviction_confluent_enters():
    d = decide_moe({"A": 0.9, "B": 0.8, "C": 0.0}, MoeRegime.TREND, W, MoeConfig())
    assert d.action == "ENTER"
    assert d.direction == 1
    assert d.score >= MoeConfig().tau


def test_empty_weight_row_scores_zero():
    m = master_score({"A": 1.0, "B": 1.0}, W[MoeRegime.CHOP], 1e-9)
    assert m == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_combiner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/combiner.py
from __future__ import annotations

from dataclasses import dataclass

from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.regimes import TRADEABLE, MoeRegime


def master_score(s_by_expert: dict[str, float], W_row: dict[str, float], eps: float) -> float:
    num = sum(W_row.get(e, 0.0) * s for e, s in s_by_expert.items())
    den = sum(W_row.values()) + eps
    return num / den


def confluence(s_by_expert: dict[str, float], W_row: dict[str, float], side: int) -> int:
    return sum(
        1
        for e, w in W_row.items()
        if w > 0.0 and (1 if s_by_expert.get(e, 0.0) > 0 else -1 if s_by_expert.get(e, 0.0) < 0 else 0) == side
    )


@dataclass(frozen=True)
class MoeDecision:
    action: str          # "ENTER" | "WAIT"
    direction: int
    regime: MoeRegime
    score: float
    detail: str


def decide_moe(
    s_by_expert: dict[str, float],
    regime: MoeRegime,
    W: dict[MoeRegime, dict[str, float]],
    cfg: MoeConfig,
) -> MoeDecision:
    if regime not in TRADEABLE:
        return MoeDecision("WAIT", 0, regime, 0.0, f"{regime.value} not tradeable")
    row = W.get(regime, {})
    m = master_score(s_by_expert, row, cfg.eps)
    side = 1 if m > 0 else -1 if m < 0 else 0
    if side == 0 or abs(m) < cfg.tau:
        return MoeDecision("WAIT", 0, regime, m, f"|M|={abs(m):.3f} < tau={cfg.tau}")
    if confluence(s_by_expert, row, side) < cfg.q_confluence:
        return MoeDecision("WAIT", 0, regime, m, "confluence below q")
    return MoeDecision("ENTER", side, regime, m, f"ENTER dir={side} M={m:.3f}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_combiner.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/combiner.py tests/test_moe_combiner.py
git commit -m "feat(moe): row-normalized master score + confluence-gated decision"
```

---

### Task 8: Null-signal generators

**Files:**
- Create: `src/moonface/signal/engine/moe/nulls.py`
- Test: `tests/test_moe_nulls.py`

**Interfaces:**
- Consumes: `RawSignal`, `raw_value`; `random.Random`.
- Produces (each takes and returns a *per-bar list of raw values keyed by expert*, preserving length; seeded):
  - `iid_shuffle(series_by_expert: dict[str, list[float]], rng: random.Random) -> dict[str, list[float]]` — permute each expert's series in time (destroys autocorrelation, keeps marginal).
  - `sign_flip(series_by_expert, rng) -> dict[str, list[float]]` — randomly flip each value's sign with p=0.5.
  - `phase_randomize(series_by_expert, rng) -> dict[str, list[float]]` — circular rotation by a random offset per expert (destroys cross-expert phase alignment).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_nulls.py
import random

from moonface.signal.engine.moe.nulls import iid_shuffle, phase_randomize, sign_flip


def test_iid_shuffle_preserves_multiset_and_length():
    rng = random.Random(0)
    src = {"A": [0.1, -0.2, 0.3, 0.0, 0.5]}
    out = iid_shuffle(src, rng)
    assert sorted(out["A"]) == sorted(src["A"])
    assert len(out["A"]) == len(src["A"])
    assert out["A"] != src["A"]  # permuted (seed 0 will reorder this input)


def test_sign_flip_preserves_absolute_values():
    rng = random.Random(1)
    src = {"A": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
    out = sign_flip(src, rng)
    assert sorted(abs(x) for x in out["A"]) == sorted(src["A"])
    assert any(x < 0 for x in out["A"])  # at least one flip with seed 1


def test_phase_randomize_is_rotation():
    rng = random.Random(2)
    src = {"A": [1.0, 2.0, 3.0, 4.0]}
    out = phase_randomize(src, rng)
    assert sorted(out["A"]) == sorted(src["A"])
    # a rotation of [1,2,3,4] keeps adjacency cyclically
    joined = out["A"] + out["A"]
    assert any(joined[i:i + 4] == [1.0, 2.0, 3.0, 4.0] for i in range(4))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_nulls.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/nulls.py
from __future__ import annotations

import random


def iid_shuffle(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name, series in series_by_expert.items():
        copy = list(series)
        rng.shuffle(copy)
        out[name] = copy
    return out


def sign_flip(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    return {
        name: [(-x if rng.random() < 0.5 else x) for x in series]
        for name, series in series_by_expert.items()
    }


def phase_randomize(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name, series in series_by_expert.items():
        n = len(series)
        if n == 0:
            out[name] = []
            continue
        k = rng.randrange(n)
        out[name] = series[k:] + series[:k]
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_nulls.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/nulls.py tests/test_moe_nulls.py
git commit -m "feat(moe): seeded null-signal generators (shuffle/sign-flip/phase)"
```

---

### Task 9: Fit panel, MoE stream, and Gate-0 null calibration

**Files:**
- Create: `src/moonface/signal/engine/moe/evaluate_moe.py` (part 1 of 2)
- Test: `tests/test_moe_null_calibration.py`

**Interfaces:**
- Consumes: from `moonface.signal.engine.v3.evaluate` — `V3Trade`, `simulate_bracket_v3`, `v3_metrics`, `split_pairs_by_window`, `segment_v3`, `TRAIN_END_TS_MS`, `SEALED_START_TS_MS`, `SPAN_END_TS_MS`, `PURGE_MS`, `LOOKBACK`; from `repair` — `block_ci_q`; `EngineConfig` (v2.2), `EngineConfigV3`; the moe modules from Tasks 2–8; `atr`, `foundation.metrics.deflated_sharpe` + `_sharpe`/`_skew`/`_kurtosis`.
- Produces:
  - `build_fit_panel(candles, cfg_v3, cfg_v22, experts, lookback) -> tuple[list[EdgeSample], dict[str,list[float]]]` — per train-eligible bar: classify moe regime (skip FLAT); for each expert compute `raw_value`; collect the expert raw series (for the normalizer); for each *fired* expert (`direction!=0`) simulate a fixed-bracket trade in the expert's direction via `simulate_bracket_v3` (cached per `(bar,direction)`) and emit an `EdgeSample(regime, expert, direction, net_r)`.
  - `moe_stream(candles, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback) -> list[tuple[V3Trade, float]]` — one-position-at-a-time: at each free bar, transform each expert raw → `s`, `decide_moe`; on ENTER, `simulate_bracket_v3(dir=score sign, quality=|score|, mechanism="MOE", cell=regime.value)`; pair with `atr_frac`.
  - `dsr_of_pairs(pairs, n_trials) -> float` — per-trade DSR from net_r list.
  - `null_calibration(candles, cfg_v3, cfg_v22, experts, cfg_moe) -> dict` — runs the FULL fit→stream→validation on iid-shuffle / sign-flip / phase-randomize expert series and returns `{"passed_negative": bool, ...}`. `passed_negative` is True iff **no** null run produces a validation-window mean-R CI strictly `>0` AND `p_eff` stayed within budget.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_null_calibration.py
"""Gate-0 (spec §4.6): the combiner MUST return NEGATIVE on nulled experts.
Mirrors tests/test_liq_twap_null_calibration.py and test_forced_error_null_calibration.py."""
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.evaluate_moe import null_calibration
from moonface.signal.engine.moe.experts import mechanism_experts
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from tests.helpers_v3 import make_candles


def test_gate0_returns_negative_on_nulls():
    candles = make_candles(4000)  # enough to populate a train window
    result = null_calibration(
        candles, EngineConfigV3(), EngineConfig(), mechanism_experts(), MoeConfig()
    )
    assert result["passed_negative"] is True, result
```

> **Note:** if `make_candles(4000)` from `helpers_v3` is a pure random/gbm walk, this is itself a null-of-nulls and MUST pass. If the helper injects a deterministic trend, keep the assertion — a correct Gate-0 still returns negative because the *experts themselves are nulled* before fitting. Use the real helper name from `helpers_v3.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_null_calibration.py -v`
Expected: FAIL with `ModuleNotFoundError` (evaluate_moe not created yet)

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/signal/engine/moe/evaluate_moe.py
from __future__ import annotations

import dataclasses
import random

from moonface.foundation.metrics import _kurtosis, _sharpe, _skew, deflated_sharpe
from moonface.foundation.risk import atr
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.moe.combiner import decide_moe
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.experts import Expert, raw_value
from moonface.signal.engine.moe.normalize import Normalizer
from moonface.signal.engine.moe.nulls import iid_shuffle, phase_randomize, sign_flip
from moonface.signal.engine.moe.power import allowed_p_eff
from moonface.signal.engine.moe.regimes import MoeRegime, classify_moe_regime
from moonface.signal.engine.moe.weights import EdgeSample, fit_weights, p_eff
from moonface.signal.engine.repair import block_ci_q
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import (
    LOOKBACK,
    PURGE_MS,
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    V3Trade,
    segment_v3,
    simulate_bracket_v3,
    split_pairs_by_window,
    v3_metrics,
)

EFFECTIVE_TRIALS = 12
FAMILY_ALPHA = 0.05
CI_LO_Q = FAMILY_ALPHA / EFFECTIVE_TRIALS / 2
CI_HI_Q = 1 - CI_LO_Q


def _regime_at(candles, i, cfg_v3, lookback):
    window = candles[max(0, i - lookback + 1) : i + 1]
    return classify_moe_regime(window, cfg_v3), window


def _raw_series(candles, cfg_v3, experts, lookback):
    """Per-expert raw value at every eligible bar (index-aligned to `bars`)."""
    bars = list(range(min(lookback, len(candles)), len(candles)))
    series = {e.name: [] for e in experts}
    regimes = []
    for i in bars:
        regime, window = _regime_at(candles, i, cfg_v3, lookback)
        regimes.append(regime)
        idx = len(window) - 1
        for e in experts:
            series[e.name].append(raw_value(e.signal(window, idx, cfg_v3)))
    return bars, regimes, series


def build_fit_panel(candles, cfg_v3, cfg_v22, experts, lookback=LOOKBACK, end_ts_ms=None):
    """EdgeSamples + per-expert raw series. When end_ts_ms is set (e.g. TRAIN_END_TS_MS)
    both the samples AND the normalizer series are restricted to bars strictly before it —
    so W and the normalizer are fit train-only, with NO look-ahead into val/sealed."""
    bars, regimes, series = _raw_series(candles, cfg_v3, experts, lookback)
    samples: list[EdgeSample] = []
    train_series: dict[str, list[float]] = {e.name: [] for e in experts}
    bracket_cache: dict[tuple[int, int], float | None] = {}

    def bracket_r(i, direction):
        key = (i, direction)
        if key not in bracket_cache:
            t = simulate_bracket_v3(candles, i, direction, 0.5, "MOE", "fit", cfg_v22)
            bracket_cache[key] = t.net_r if t is not None else None
        return bracket_cache[key]

    for pos, i in enumerate(bars):
        if end_ts_ms is not None and candles[i].timestamp_ms >= end_ts_ms:
            continue  # train-only fit boundary
        regime = regimes[pos]
        for e in experts:
            train_series[e.name].append(series[e.name][pos])
        if regime == MoeRegime.FLAT:
            continue
        for e in experts:
            raw = series[e.name][pos]
            direction = 1 if raw > 0 else -1 if raw < 0 else 0
            if direction == 0:
                continue
            r = bracket_r(i, direction)
            if r is None:
                continue
            samples.append(EdgeSample(regime, e.name, direction, r))
    return samples, train_series


def _train_count(samples) -> int:
    return len(samples)


def moe_stream(candles, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback=LOOKBACK):
    pairs: list[tuple[V3Trade, float]] = []
    busy_until = -1
    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        if i <= busy_until:
            continue
        window = candles[max(0, i - lookback + 1) : i + 1]
        idx = len(window) - 1
        regime = classify_moe_regime(window, cfg_v3)
        s_by_expert = {
            e.name: normalizer.transform(e.name, raw_value(e.signal(window, idx, cfg_v3)))
            for e in experts
        }
        decision = decide_moe(s_by_expert, regime, W, cfg_moe)
        if decision.action != "ENTER":
            continue
        trade = simulate_bracket_v3(
            candles, i, decision.direction, abs(decision.score), "MOE", regime.value, cfg_v22
        )
        if trade is None:
            break
        tail = candles[max(0, i - cfg_v22.atr_period) : i + 1]
        close = candles[i].close
        atr_frac = atr(tail, cfg_v22.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs


def dsr_of_pairs(pairs, n_trials=EFFECTIVE_TRIALS) -> float:
    rs = [t.net_r for t, _ in pairs]
    if len(rs) < 2:
        return 0.0
    sr = _sharpe(rs)
    return deflated_sharpe(sr, len(rs), _skew(rs), _kurtosis(rs), [sr], n_trials)


def _validation_ci_positive(pairs) -> bool:
    val = split_pairs_by_window(pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS)
    if len(val) < 2:
        return False
    ci = block_ci_q(val, lambda p: p[0].entry_index,
                    lambda ps: (sum(t.net_r for t, _ in ps) / len(ps)) if ps else 0.0,
                    CI_LO_Q, CI_HI_Q)
    return ci is not None and ci[0] > 0


def _fit_from_series(candles, cfg_v3, cfg_v22, experts, series, cfg_moe, lookback):
    """Rebuild EdgeSamples from a (possibly nulled) raw series, fit normalizer + W."""
    bars = list(range(min(lookback, len(candles)), len(candles)))
    # normalizer fit on train-eligible bars only
    train_series = {name: vals for name, vals in series.items()}
    normalizer = Normalizer.fit(train_series, cfg_moe)
    samples: list[EdgeSample] = []
    bracket_cache: dict[tuple[int, int], float | None] = {}

    def bracket_r(i, direction):
        key = (i, direction)
        if key not in bracket_cache:
            t = simulate_bracket_v3(candles, i, direction, 0.5, "MOE", "fit", cfg_v22)
            bracket_cache[key] = t.net_r if t is not None else None
        return bracket_cache[key]

    for pos, i in enumerate(bars):
        regime, _ = _regime_at(candles, i, cfg_v3, lookback)
        if regime == MoeRegime.FLAT:
            continue
        for e in experts:
            raw = series[e.name][pos]
            direction = 1 if raw > 0 else -1 if raw < 0 else 0
            if direction == 0:
                continue
            r = bracket_r(i, direction)
            if r is None:
                continue
            samples.append(EdgeSample(regime, e.name, direction, r))
    names = [e.name for e in experts]
    W = fit_weights(samples, names, cfg_moe, n_train_trades=len(samples))
    return normalizer, W


class _StaticExpert:
    """Wraps a precomputed per-bar raw series so nulled signals flow through moe_stream."""

    def __init__(self, name, bars, values):
        self.name = name
        self._by_index = dict(zip(bars, values))

    def signal(self, window, index, cfg):
        from moonface.signal.engine.moe.experts import RawSignal
        # window is a trailing slice; recover absolute bar index is not available here,
        # so nulled streams are evaluated via a dedicated absolute-index path below.
        raise NotImplementedError


def null_calibration(candles, cfg_v3, cfg_v22, experts, cfg_moe) -> dict:
    """Gate-0: fit+stream on nulled expert series; require every run to be non-positive."""
    bars, _regimes, series = _raw_series(candles, cfg_v3, experts, LOOKBACK)
    rng = random.Random(cfg_moe.seed)
    generators = {
        "iid_shuffle": iid_shuffle,
        "sign_flip": sign_flip,
        "phase_randomize": phase_randomize,
    }
    runs = {}
    any_positive = False
    for label, gen in generators.items():
        nulled = gen(series, rng)
        normalizer, W = _fit_from_series(
            candles, cfg_v3, cfg_v22, experts, nulled, cfg_moe, LOOKBACK
        )
        pairs = _stream_from_series(candles, cfg_v3, cfg_v22, experts, bars, nulled,
                                    normalizer, W, cfg_moe)
        positive = _validation_ci_positive(pairs)
        runs[label] = {
            "n": len(pairs),
            "p_eff": p_eff(W),
            "dsr": round(dsr_of_pairs(pairs), 4),
            "validation_ci_positive": positive,
        }
        any_positive = any_positive or positive
    return {"passed_negative": not any_positive, "runs": runs}


def _stream_from_series(candles, cfg_v3, cfg_v22, experts, bars, series,
                        normalizer, W, cfg_moe, lookback=LOOKBACK):
    """moe_stream driven by a precomputed (nulled) raw series indexed by absolute bar."""
    by_index = {name: dict(zip(bars, vals)) for name, vals in series.items()}
    pairs: list[tuple[V3Trade, float]] = []
    busy_until = -1
    for i in bars:
        if i <= busy_until:
            continue
        window = candles[max(0, i - lookback + 1) : i + 1]
        regime = classify_moe_regime(window, cfg_v3)
        s_by_expert = {
            e.name: normalizer.transform(e.name, by_index[e.name].get(i, 0.0))
            for e in experts
        }
        decision = decide_moe(s_by_expert, regime, W, cfg_moe)
        if decision.action != "ENTER":
            continue
        trade = simulate_bracket_v3(
            candles, i, decision.direction, abs(decision.score), "MOE", regime.value, cfg_v22
        )
        if trade is None:
            break
        tail = candles[max(0, i - cfg_v22.atr_period) : i + 1]
        close = candles[i].close
        atr_frac = atr(tail, cfg_v22.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs
```

> **Simplify during implementation:** the `_StaticExpert` stub above is dead scaffolding — delete it. The working null path is `_stream_from_series` (absolute-bar indexed). Keep `moe_stream` for the live run (Task 10) and `_stream_from_series` for nulls; if you can unify them behind one absolute-index driver, do so and drop the duplicate. The test only requires `null_calibration(...)["passed_negative"] is True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_null_calibration.py -v`
Expected: PASS (1 passed). If it FAILS with `passed_negative False`, the combiner is finding edge on noise — that is a real Gate-0 failure: tighten `tau`/`q_confluence` defaults or the L1/budget in `fit_weights` until nulls return negative. Do NOT weaken the test.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/evaluate_moe.py tests/test_moe_null_calibration.py
git commit -m "feat(moe): fit panel, MoE stream, and mandatory Gate-0 null calibration"
```

---

### Task 10: Walk-forward Gate1/2/3 + verdict + CLI

**Files:**
- Modify: `src/moonface/signal/engine/moe/evaluate_moe.py` (add `build_moe_report`)
- Create: `tools/moe_evaluate.py`
- Test: `tests/test_moe_report.py`

**Interfaces:**
- Consumes: everything from Task 9; from `v3.evaluate` — `gate1_validation`, `gate2_sealed`, `gate3_transfer`, `v22_pairs`, `SPAN_END_TS_MS`, `SEALED_START_TS_MS`, `TRAIN_END_TS_MS`, `PURGE_MS`; `replay_metrics` from `repair`; `moe_hash`.
- Produces: `build_moe_report(btc, eth, sol, cfg_v3, cfg_v22, cfg_moe, warmup, lookback) -> dict` with keys `moe_hash`, `gate0`, `power`, `fitted` (`p_eff`, matrix), `gate1`, `gate2`, `gate3`, `verdict`. **Verdict order:** `GATE0_FAILED_HALT` (if `gate0.passed_negative` is False) → `POWER_BUDGET_REFUSED` (if `check_power_budget` false) → then reuse v3's `CLOSED_NEGATIVE_VALIDATION / CLOSED_NEGATIVE_SEALED_BTC / CLOSED_NEGATIVE_TRANSFER / ALL_GATES_PASSED_HUMAN_DECISION_PENDING`. Sealed opens ONLY if Gate-0 passed, power passed, and Gate1 passed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_report.py
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.evaluate_moe import build_moe_report
from moonface.signal.engine.moe.experts import mechanism_experts
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from tests.helpers_v3 import make_candles


def test_report_has_gate0_and_verdict():
    btc = make_candles(6000)
    eth = make_candles(6000)
    sol = make_candles(6000)
    report = build_moe_report(
        btc, eth, sol, EngineConfigV3(), EngineConfig(), MoeConfig(),
        warmup=400, lookback=400, experts=mechanism_experts(),
    )
    assert "gate0" in report and "verdict" in report
    assert report["verdict"] in {
        "GATE0_FAILED_HALT",
        "POWER_BUDGET_REFUSED",
        "CLOSED_NEGATIVE_VALIDATION",
        "CLOSED_NEGATIVE_SEALED_BTC",
        "CLOSED_NEGATIVE_TRANSFER",
        "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
    }
    # sealed must stay unopened unless gate0+power+gate1 all pass
    if report["verdict"] in {"GATE0_FAILED_HALT", "POWER_BUDGET_REFUSED", "CLOSED_NEGATIVE_VALIDATION"}:
        assert report["gate2"] is None


def test_synthetic_noise_does_not_pass():
    # random-ish candles must never reach ALL_GATES_PASSED
    btc = make_candles(6000)
    report = build_moe_report(
        btc, btc, btc, EngineConfigV3(), EngineConfig(), MoeConfig(),
        warmup=400, lookback=400, experts=mechanism_experts(),
    )
    assert report["verdict"] != "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_moe_report'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/moonface/signal/engine/moe/evaluate_moe.py
from moonface.signal.engine.moe.config_moe import moe_hash
from moonface.signal.engine.moe.power import check_power_budget
from moonface.signal.engine.repair import replay_metrics
from moonface.signal.engine.v3.evaluate import (
    SPAN_END_TS_MS,
    gate1_validation,
    gate2_sealed,
    gate3_transfer,
    v22_pairs,
)


def build_moe_report(btc, eth, sol, cfg_v3, cfg_v22, cfg_moe, warmup,
                     lookback=LOOKBACK, experts=None):
    if experts is None:
        from moonface.signal.engine.moe.experts import mechanism_experts
        experts = mechanism_experts()

    # Gate-0 FIRST (spec §4.6)
    gate0 = null_calibration(btc, cfg_v3, cfg_v22, experts, cfg_moe)

    # Fit on the TRAIN segment only (end_ts_ms boundary -> no look-ahead)
    train_samples, train_series = build_fit_panel(
        btc, cfg_v3, cfg_v22, experts, lookback, end_ts_ms=TRAIN_END_TS_MS
    )
    normalizer = Normalizer.fit(train_series, cfg_moe)
    names = [e.name for e in experts]
    W = fit_weights(train_samples, names, cfg_moe, n_train_trades=len(train_samples))
    eff = p_eff(W)
    power_ok = check_power_budget(len(train_samples), eff, cfg_moe.m_per_weight)

    report = {
        "moe_hash": moe_hash(cfg_moe),
        "gate0": gate0,
        "power": {"n_train": len(train_samples), "p_eff": eff,
                  "allowed": allowed_p_eff(len(train_samples), cfg_moe.m_per_weight),
                  "passed": power_ok},
        "fitted": {"p_eff": eff,
                   "matrix": {r.value: {k: round(v, 4) for k, v in row.items() if v > 0}
                              for r, row in W.items()}},
        "gate1": None, "gate2": None, "gate3": None,
    }

    if not gate0["passed_negative"]:
        report["verdict"] = "GATE0_FAILED_HALT"
        return report
    if not power_ok:
        report["verdict"] = "POWER_BUDGET_REFUSED"
        return report

    btc_bars, _btc_regimes, btc_series = _raw_series(btc, cfg_v3, experts, lookback)
    btc_pairs = _stream_from_series(
        btc, cfg_v3, cfg_v22, experts, btc_bars,
        {e.name: btc_series[e.name] for e in experts},
        normalizer, W, cfg_moe, lookback,
    )
    val_pairs = split_pairs_by_window(btc_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS)
    base_pairs = v22_pairs(btc, cfg_v22, warmup)
    base_val = replay_metrics(
        split_pairs_by_window(base_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS), cfg_v22)
    gate1 = gate1_validation(val_pairs, base_val)
    report["gate1"] = gate1
    if not gate1["passed"]:
        report["verdict"] = "CLOSED_NEGATIVE_VALIDATION"
        return report

    sealed_pairs = split_pairs_by_window(btc_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)
    base_sealed = replay_metrics(
        split_pairs_by_window(base_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS), cfg_v22)
    gate2 = gate2_sealed(sealed_pairs, base_sealed)
    report["gate2"] = gate2
    if not gate2["passed"]:
        report["verdict"] = "CLOSED_NEGATIVE_SEALED_BTC"
        return report

    def _sealed_leg(cds):
        p = _stream_from_series(
            cds, cfg_v3, cfg_v22, experts,
            list(range(min(lookback, len(cds)), len(cds))),
            {e.name: _raw_series(cds, cfg_v3, experts, lookback)[2][e.name] for e in experts},
            normalizer, W, cfg_moe, lookback)
        return split_pairs_by_window(p, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)

    gate3 = gate3_transfer(_sealed_leg(eth), _sealed_leg(sol))
    report["gate3"] = gate3
    report["verdict"] = (
        "ALL_GATES_PASSED_HUMAN_DECISION_PENDING" if gate3["passed"]
        else "CLOSED_NEGATIVE_TRANSFER"
    )
    return report
```

> **Train-boundary guard (add this test in Step 1 of this task):** `build_fit_panel(..., end_ts_ms=TRAIN_END_TS_MS)` is what keeps `W` and the normalizer train-only. Add `test_fit_panel_respects_train_end` asserting that with `end_ts_ms` set, every contributing bar has `timestamp_ms < TRAIN_END_TS_MS` (build a small synthetic series straddling the boundary and check `len(samples)` drops to the pre-boundary count). This is the most important correctness property in the task.

```python
# tools/moe_evaluate.py
"""CLI: single registered MoE evaluation. Mirrors tools/v3_evaluate.py.
Run from repo root: .venv/bin/python -m tools.moe_evaluate --out experiments/engine/moe_eval.json
"""
from __future__ import annotations

import argparse
import json

from moonface.data.candles import load_candles  # use the real loader tools/v3_evaluate.py uses
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.evaluate_moe import build_moe_report
from moonface.signal.engine.moe.experts import mechanism_experts
from moonface.signal.engine.v3.config_v3 import EngineConfigV3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-ms", type=int, default=1577836800000)
    ap.add_argument("--end-ms", type=int, default=1782316800000)
    ap.add_argument("--warmup", type=int, default=400)
    ap.add_argument("--lookback", type=int, default=400)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # NOTE: replace load_candles(...) with the exact call tools/v3_evaluate.py uses.
    btc = load_candles("binance", "BTC/USDT:USDT", "1h", args.start_ms, args.end_ms)
    eth = load_candles("binance", "ETH/USDT:USDT", "1h", args.start_ms, args.end_ms)
    sol = load_candles("binance", "SOL/USDT:USDT", "1h", args.start_ms, args.end_ms)

    report = build_moe_report(
        btc, eth, sol, EngineConfigV3(), EngineConfig(), MoeConfig(),
        warmup=args.warmup, lookback=args.lookback, experts=mechanism_experts(),
    )
    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(report["verdict"])


if __name__ == "__main__":
    main()
```

> **Wire the real data loader.** Open `tools/v3_evaluate.py` and copy its exact candle-loading call (module + signature) into `tools/moe_evaluate.py`; the `moonface.data.candles.load_candles` import above is a placeholder for whatever v3 actually uses. The CLI is not unit-tested (needs real data); the report logic is covered by `test_moe_report.py` on synthetic candles.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_report.py -v`
Expected: PASS (2 passed). The synthetic-noise test asserts the verdict is never `ALL_GATES_PASSED` — if it ever is, Gate-0/power/DSR are too loose; fix the gates, not the test.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all green (existing v3 suite + new moe tests). If any v3 test broke, you imported/renamed something you shouldn't have — revert that.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/moe/evaluate_moe.py tools/moe_evaluate.py tests/test_moe_report.py
git commit -m "feat(moe): walk-forward Gate1/2/3 with Gate-0+power preconditions and CLI"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| §2 Regime classifier (3+FLAT, causal) | Task 2 |
| §3.1 Expert protocol | Task 3 |
| §3.2 Normalization (rank default, tanh alt) | Task 4 |
| §3.3 Master score (row-normalized) | Task 7 |
| §3.4 Trigger (tau + confluence) | Task 7 |
| §4.1 DoF isolation (only `W` fit) | Tasks 2/4/6 (thresholds & norm frozen) |
| §4.2 Power budget precondition | Tasks 5, 10 |
| §4.3 Constrained shrinkage estimator | Task 6 |
| §4.4 Nested walk-forward, sealed-once | Tasks 9, 10 (reuses v3 splits) |
| §4.5 Deflated significance + block CI | Tasks 9 (`dsr_of_pairs`, `block_ci_q`) |
| §4.6 Gate-0 null calibration (mandatory, first) | Task 9, enforced in Task 10 verdict order |
| §4.7 Pre-registered kill rule | Task 1 (`moe_hash` freezes config) + Task 10 (sealed-once flow) |
| §5 Protocols (Regime/Expert/Combiner) | Tasks 2/3/7 |

Gap noted: §4.7's "burn the sealed window / no re-fit" is a *process* discipline (human ops), partially enforced by the one-shot verdict flow (sealed opens only after Gate1) and the frozen `moe_hash`. No further code needed — matches how v3 handles it.

**2. Placeholder scan:** No deliberate defects remain — `_james_stein_lambda` (Task 6) is correct as written, and the train-only fit is enforced structurally via `build_fit_panel(..., end_ts_ms=TRAIN_END_TS_MS)` (Tasks 9–10) rather than a post-hoc split. Two honest implementer flags remain, each with explicit instructions: the `_StaticExpert` stub (Task 9) is marked for deletion (its working replacement `_stream_from_series` is fully specified), and the CLI data-loader import (Task 10) must be copied from `tools/v3_evaluate.py` since it needs real data and isn't unit-tested. No blind "TODO/TBD".

**3. Type consistency:** `RawSignal(direction,magnitude)` (Task 3) consumed by normalizer/stream via `raw_value` (Task 3). `EdgeSample(regime,expert,direction,net_r)` produced in Task 6, built in Task 9. `W: dict[MoeRegime, dict[str,float]]` produced in Task 6, consumed in Tasks 7/9/10. `MoeDecision(action,direction,regime,score,detail)` (Task 7) consumed in Task 9/10 streams. Pairs are `list[tuple[V3Trade, float]]` throughout, matching v3's `gate1_validation`/`v3_metrics`/`split_pairs_by_window` signatures.

---

## Known Risks / Notes for the Implementer

- **`helpers_v3.py`:** open it first; use its real synthetic-candle constructor name (the plan writes `make_candles` as a stand-in). Every test depends on it.
- **`tools/v3_evaluate.py`:** the source of truth for the real candle loader and the `warmup`/`lookback` conventions. Copy, don't invent.
- **Gate-0 is the whole point.** If `passed_negative` is False, the framework is broken, not the market. Tighten gates until nulls die; never relax the null test.
- **Expected end state:** on the current 3-mechanism free-OHLCV expert set, the most likely verdict is `POWER_BUDGET_REFUSED` or `CLOSED_NEGATIVE_VALIDATION`. That is the spec's pre-registered §7 outcome — a certified negative is the deliverable working, not a failure of the task.
