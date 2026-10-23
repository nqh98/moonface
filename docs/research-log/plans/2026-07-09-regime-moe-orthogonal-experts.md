# Regime-MoE Orthogonal-Expert Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two frozen non-price experts (FUNDING, OI) to the MoE combiner and test — under the unchanged anti-artifact protocol — whether regime-conditioned weighting of orthogonal data contributes edge.

**Architecture:** Widen the `Expert` interface to an `ExpertContext` carrying aligned funding/OI series; price experts ignore them, two new experts read them. Thread funding/OI from `build_moe_report` (now bundle-input) down to the single call site (`_raw_series`). Add an `identity_hash` folding the expert set + frozen constants into a tamper-evident trial identity. All gates (Gate-0 first, power, sealed-once) reused verbatim.

**Tech Stack:** Python 3.12, stdlib only, pytest. Reuses `moonface.foundation.bundle.DataBundle`, `moonface.signal.engine.v3.*`, existing `moonface.signal.engine.moe.*`.

## Global Constraints

- **Spec:** `docs/research-log/specs/2026-07-09-regime-moe-orthogonal-experts-design.md`. Every task implements a section.
- **Only `W` is fit to returns.** Expert transforms, `FUNDING_CAP`, `OI_LOOKBACK`, thresholds, and normalizer stats are frozen from theory or train-only descriptive stats. Do not fit anything else to returns.
- **Causality:** every feature at bar `t` uses only data with index ≤ `t` (as-of-aligned funding/OI, closes ≤ t). Trades still enter at `t+1`.
- **Frozen constants (verbatim):** `FUNDING_CAP = 0.01`, `OI_LOOKBACK = 24`.
- **Reuse, do not fork, existing primitives:** `simulate_bracket_v3`, `gate1_validation`, `gate2_sealed`, `gate3_transfer`, `v22_pairs`, `split_pairs_by_window`, `Normalizer`, `fit_weights`, `p_eff`, `decide_moe`, and the split constants. Import them; never redefine.
- **`moe_hash` signature stays stable** (existing callers depend on it). Add `identity_hash` alongside it.
- **House conventions (OVERRIDE SDD defaults):** implementer subagents are Write/Edit/Read-only (no Bash) — write test+impl, self-review by reading back, write report; do NOT run pytest or commit. **Controller** runs `.venv/bin/python -m pytest` (focused + full) + `.venv/bin/ruff check`, stages NAMED paths, verifies `git diff --cached --stat`, commits (NO AI-attribution trailer). Entrypoint `.venv/bin/python` (3.12; never bare `python`/`pytest`). `docs/` needs `git add -f`; `experiments/` is tracked (plain add).
- **Determinism:** all bootstrap/shuffle uses seeded `random.Random`; seed lives in `MoeConfig`.

---

## File Structure

- `src/moonface/signal/engine/moe/config_moe.py` — MODIFY: add `identity_hash`.
- `src/moonface/signal/engine/moe/experts.py` — MODIFY: `ExpertContext`, new `Expert.signal(ctx)` signature, adapt `_MechanismExpert`, add `_FundingExpert`/`_OiExpert`, frozen constants, `orthogonal_experts()`, `default_experts()`.
- `src/moonface/signal/engine/moe/evaluate_moe.py` — MODIFY: `_raw_series` builds `ExpertContext`; thread `funding`/`oi` through its 4 direct callers; `build_moe_report` takes `DataBundle`s, uses `default_experts()`, records `experts`/`identity_hash`/`ortho_constants`.
- `tools/moe_evaluate.py` — MODIFY: MoE asset dicts gain `funding_symbol` + `metrics_field`, pass bundles, add `--experts`.
- `tests/test_moe_identity_hash.py` — CREATE.
- `tests/test_moe_orthogonal_experts.py` — CREATE.
- `tests/test_moe_experts.py` — MODIFY: new signature.
- `tests/test_moe_report.py` — MODIFY: bundle inputs + 5 experts.
- `tests/test_moe_null_calibration.py` — MODIFY: 5-expert non-vacuous Gate-0.
- `tests/test_moe_cli.py` — MODIFY: `--experts` + asset dicts.
- `experiments/engine/MOE_ORTHO_REGISTRATION.md` — CREATE (pre-registration, before run).

---

### Task 1: `identity_hash` — expert-set-aware trial identity

**Files:**
- Modify: `src/moonface/signal/engine/moe/config_moe.py`
- Test: `tests/test_moe_identity_hash.py`

**Interfaces:**
- Consumes: `MoeConfig`, `moe_hash`, `MOE_VERSION` (existing in the module).
- Produces: `identity_hash(cfg: MoeConfig, expert_names: list[str], ortho_constants: dict) -> str` — sha256 over `moe_hash(cfg)` + sorted expert names + sorted ortho constants + version. `moe_hash` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_identity_hash.py
import dataclasses

from moonface.signal.engine.moe.config_moe import MoeConfig, identity_hash, moe_hash

CONSTS = {"FUNDING_CAP": 0.01, "OI_LOOKBACK": 24}


def test_identity_hash_is_stable_and_64_hex():
    h1 = identity_hash(MoeConfig(), ["A", "B"], CONSTS)
    h2 = identity_hash(MoeConfig(), ["B", "A"], CONSTS)  # order-insensitive
    assert h1 == h2 and len(h1) == 64


def test_identity_hash_changes_with_expert_set():
    base = identity_hash(MoeConfig(), ["BREAKOUT", "PULLBACK", "REVERSION"], CONSTS)
    more = identity_hash(MoeConfig(), ["BREAKOUT", "PULLBACK", "REVERSION", "FUNDING", "OI"], CONSTS)
    assert base != more


def test_identity_hash_changes_with_config_and_constants():
    a = identity_hash(MoeConfig(), ["A"], CONSTS)
    b = identity_hash(dataclasses.replace(MoeConfig(), q_confluence=1), ["A"], CONSTS)
    c = identity_hash(MoeConfig(), ["A"], {"FUNDING_CAP": 0.02, "OI_LOOKBACK": 24})
    assert a != b and a != c
    # differs from plain moe_hash (identity carries more than the config)
    assert a != moe_hash(MoeConfig())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_identity_hash.py -v`
Expected: FAIL with `ImportError: cannot import name 'identity_hash'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/moonface/signal/engine/moe/config_moe.py`:

```python
def identity_hash(cfg: MoeConfig, expert_names: list[str], ortho_constants: dict) -> str:
    payload = {
        "moe_hash": moe_hash(cfg),
        "experts": sorted(expert_names),
        "ortho_constants": {k: ortho_constants[k] for k in sorted(ortho_constants)},
        "__moe_version__": MOE_VERSION,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_identity_hash.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/config_moe.py tests/test_moe_identity_hash.py
git commit -m "feat(moe): identity_hash folds expert set + ortho constants into trial identity"
```

---

### Task 2: `ExpertContext` + FUNDING/OI experts + thread funding/OI internally

**Files:**
- Modify: `src/moonface/signal/engine/moe/experts.py`
- Modify: `src/moonface/signal/engine/moe/evaluate_moe.py`
- Test: `tests/test_moe_orthogonal_experts.py` (create)
- Test: `tests/test_moe_experts.py` (update to new signature)

**Interfaces:**
- Consumes: `Candle`, `EngineConfigV3`, `MECHANISMS`, `build_context`, `clip01`, `classify_regime`.
- Produces:
  - `@dataclass(frozen=True) ExpertContext(window: list[Candle], index: int, cfg: EngineConfigV3, funding: list[float|None]|None = None, oi: list[float|None]|None = None)`.
  - `Expert` protocol with `signal(self, ctx: ExpertContext) -> RawSignal`.
  - Frozen constants `FUNDING_CAP = 0.01`, `OI_LOOKBACK = 24`, `ORTHO_CONSTANTS = {"FUNDING_CAP": FUNDING_CAP, "OI_LOOKBACK": OI_LOOKBACK}`.
  - `orthogonal_experts() -> [_FundingExpert(), _OiExpert()]` (names `"FUNDING"`, `"OI"`); `default_experts() -> mechanism_experts() + orthogonal_experts()`.
  - `_raw_series(candles, cfg_v3, experts, lookback, funding=None, oi=None)` and its 4 direct callers (`build_fit_panel`, `moe_stream`, `null_calibration`, `_pairs_for_asset`) gain `funding=None, oi=None` passthrough. `build_moe_report` unchanged this task (funding/oi default None → orthogonal experts no-fire → suite stays green).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moe_orthogonal_experts.py
from moonface.foundation.models import Candle
from moonface.signal.engine.moe.experts import (
    ExpertContext,
    default_experts,
    orthogonal_experts,
)
from moonface.signal.engine.v3.config_v3 import EngineConfigV3


def _candles(n, start=100.0, step=1.0):
    out, p = [], start
    for i in range(n):
        o = p
        cl = p + step
        out.append(Candle(1_600_000_000_000 + i * 3_600_000, o, max(o, cl) + 0.2,
                          min(o, cl) - 0.2, cl, 1000.0))
        p = cl
    return out


def _ctx(candles, funding=None, oi=None):
    return ExpertContext(window=candles, index=len(candles) - 1,
                         cfg=EngineConfigV3(), funding=funding, oi=oi)


def test_names():
    assert {e.name for e in orthogonal_experts()} == {"FUNDING", "OI"}
    assert [e.name for e in default_experts()] == [
        "BREAKOUT", "PULLBACK", "REVERSION", "FUNDING", "OI"]


def test_funding_fades_the_crowd():
    funding = {e.name: e for e in orthogonal_experts()}["FUNDING"]
    c = _candles(30)
    n = len(c)
    # extreme positive funding -> SHORT bias (direction -1)
    pos = funding.signal(_ctx(c, funding=[0.0] * (n - 1) + [0.02]))
    assert pos.direction == -1 and 0.0 < pos.magnitude <= 1.0
    # extreme negative funding -> LONG bias (+1)
    neg = funding.signal(_ctx(c, funding=[0.0] * (n - 1) + [-0.02]))
    assert neg.direction == 1
    # None / zero / missing series -> no-fire
    assert funding.signal(_ctx(c, funding=None)).direction == 0
    assert funding.signal(_ctx(c, funding=[0.0] * n)).direction == 0


def test_oi_confirms_momentum():
    oi_expert = {e.name: e for e in orthogonal_experts()}["OI"]
    up = _candles(30, step=1.0)      # rising price
    n = len(up)
    rising_oi = [100.0 + i for i in range(n)]   # OI rising -> conviction
    sig = oi_expert.signal(_ctx(up, oi=rising_oi))
    assert sig.direction == 1 and 0.0 < sig.magnitude <= 1.0
    # OI falling -> no conviction regardless of price
    falling_oi = [100.0 + (n - i) for i in range(n)]
    assert oi_expert.signal(_ctx(up, oi=falling_oi)).direction == 0
    # None / insufficient history -> no-fire
    assert oi_expert.signal(_ctx(up, oi=None)).direction == 0
    assert oi_expert.signal(_ctx(_candles(10), oi=[1.0] * 10)).direction == 0  # index < OI_LOOKBACK


def test_oi_causal_uses_only_past():
    # changing a FUTURE-relative bar cannot happen: expert only reads window[:index+1];
    # verify it reads oi[index] and oi[index-OI_LOOKBACK], not beyond.
    oi_expert = {e.name: e for e in orthogonal_experts()}["OI"]
    up = _candles(30)
    n = len(up)
    oi = [100.0 + i for i in range(n)]
    base = oi_expert.signal(_ctx(up, oi=oi))
    assert base.direction == 1  # sanity
```

Also **rewrite `tests/test_moe_experts.py`** to the new signature (build an `ExpertContext`):

```python
# tests/test_moe_experts.py
from moonface.foundation.models import Candle
from moonface.signal.engine.moe.experts import (
    ExpertContext,
    RawSignal,
    mechanism_experts,
    raw_value,
)
from moonface.signal.engine.v3.config_v3 import EngineConfigV3


def _candles(n, start=100.0, step=1.0):
    out, p = [], start
    for i in range(n):
        o = p
        cl = p + step
        out.append(Candle(1_600_000_000_000 + i * 3_600_000, o, max(o, cl) + 0.2,
                          min(o, cl) - 0.2, cl, 1000.0))
        p = cl
    return out


def test_raw_value_is_signed_magnitude():
    assert raw_value(RawSignal(direction=-1, magnitude=0.4)) == -0.4
    assert raw_value(RawSignal(direction=0, magnitude=0.9)) == 0.0


def test_mechanism_experts_named_and_causal():
    experts = mechanism_experts()
    assert {e.name for e in experts} == {"BREAKOUT", "PULLBACK", "REVERSION"}
    candles = _candles(300)
    ctx = ExpertContext(window=candles, index=len(candles) - 1, cfg=EngineConfigV3())
    for e in experts:
        sig = e.signal(ctx)
        assert sig.direction in (-1, 0, 1)
        assert 0.0 <= sig.magnitude <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_moe_orthogonal_experts.py tests/test_moe_experts.py -v`
Expected: FAIL with `ImportError: cannot import name 'ExpertContext'`

- [ ] **Step 3: Rewrite `src/moonface/signal/engine/moe/experts.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from moonface.foundation.models import Candle
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.matrix import MECHANISMS
from moonface.signal.engine.v3.mechanisms.base import build_context, clip01
from moonface.signal.engine.v3.regime import classify_regime

FUNDING_CAP = 0.01
OI_LOOKBACK = 24
ORTHO_CONSTANTS = {"FUNDING_CAP": FUNDING_CAP, "OI_LOOKBACK": OI_LOOKBACK}


@dataclass(frozen=True)
class RawSignal:
    direction: int
    magnitude: float


def raw_value(sig: RawSignal) -> float:
    return sig.direction * sig.magnitude


def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


@dataclass(frozen=True)
class ExpertContext:
    window: list[Candle]
    index: int
    cfg: EngineConfigV3
    funding: list[float | None] | None = None  # aligned 1:1 to window, or None
    oi: list[float | None] | None = None        # aligned 1:1 to window, or None


class Expert(Protocol):
    name: str

    def signal(self, ctx: ExpertContext) -> RawSignal:
        ...


@dataclass(frozen=True)
class _MechanismExpert:
    name: str

    def signal(self, ctx: ExpertContext) -> RawSignal:
        regime = classify_regime(ctx.window[: ctx.index + 1], ctx.cfg)
        bar_ctx = build_context(ctx.window, ctx.index, ctx.cfg)
        sig = MECHANISMS[self.name].evaluate(bar_ctx, regime)
        return RawSignal(direction=sig.direction, magnitude=clip01(sig.quality))


@dataclass(frozen=True)
class _FundingExpert:
    name: str = "FUNDING"

    def signal(self, ctx: ExpertContext) -> RawSignal:
        if ctx.funding is None:
            return RawSignal(0, 0.0)
        f = ctx.funding[ctx.index]
        if f is None or f == 0.0:
            return RawSignal(0, 0.0)
        return RawSignal(direction=-_sign(f), magnitude=clip01(abs(f) / FUNDING_CAP))


@dataclass(frozen=True)
class _OiExpert:
    name: str = "OI"

    def signal(self, ctx: ExpertContext) -> RawSignal:
        if ctx.oi is None or ctx.index < OI_LOOKBACK:
            return RawSignal(0, 0.0)
        oi_now = ctx.oi[ctx.index]
        oi_prev = ctx.oi[ctx.index - OI_LOOKBACK]
        if oi_now is None or oi_prev is None or oi_prev <= 0.0:
            return RawSignal(0, 0.0)
        d_oi = oi_now - oi_prev
        if d_oi <= 0.0:
            return RawSignal(0, 0.0)  # positions closing -> no conviction
        d_px = ctx.window[ctx.index].close - ctx.window[ctx.index - OI_LOOKBACK].close
        return RawSignal(direction=_sign(d_px), magnitude=clip01(d_oi / oi_prev))


def mechanism_experts() -> list[Expert]:
    return [_MechanismExpert(name) for name in ("BREAKOUT", "PULLBACK", "REVERSION")]


def orthogonal_experts() -> list[Expert]:
    return [_FundingExpert(), _OiExpert()]


def default_experts() -> list[Expert]:
    return mechanism_experts() + orthogonal_experts()
```

- [ ] **Step 4: Update `_raw_series` and its 4 direct callers in `evaluate_moe.py`**

Add the import at the top of `evaluate_moe.py` (join the existing experts import line):

```python
from moonface.signal.engine.moe.experts import ExpertContext, raw_value
```

Replace `_raw_series` (lines 41-51) with:

```python
def _raw_series(candles, cfg_v3, experts, lookback, funding=None, oi=None):
    bars = list(range(min(lookback, len(candles)), len(candles)))
    series = {expert.name: [] for expert in experts}
    regimes = []
    for i in bars:
        a = max(0, i - lookback + 1)
        window = candles[a : i + 1]
        regimes.append(classify_moe_regime(window, cfg_v3))
        idx = len(window) - 1
        ctx = ExpertContext(
            window=window,
            index=idx,
            cfg=cfg_v3,
            funding=(funding[a : i + 1] if funding is not None else None),
            oi=(oi[a : i + 1] if oi is not None else None),
        )
        for expert in experts:
            series[expert.name].append(raw_value(expert.signal(ctx)))
    return bars, regimes, series
```

Thread `funding=None, oi=None` into the four direct callers and pass them to `_raw_series`:

- `build_fit_panel(candles, cfg_v3, cfg_v22, experts, lookback=LOOKBACK, end_ts_ms=None, funding=None, oi=None)` — change its internal call to `_raw_series(candles, cfg_v3, experts, lookback, funding, oi)`.
- `moe_stream(candles, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback=LOOKBACK, funding=None, oi=None)` — call `_raw_series(candles, cfg_v3, experts, lookback, funding, oi)`.
- `null_calibration(candles, cfg_v3, cfg_v22, experts, cfg_moe, funding=None, oi=None)` — first line becomes `bars, _regimes, series = _raw_series(candles, cfg_v3, experts, LOOKBACK, funding, oi)`.
- `_pairs_for_asset(candles, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback, funding=None, oi=None)` — call `_raw_series(candles, cfg_v3, experts, lookback, funding, oi)`.

Leave `build_moe_report`, `_stream_from_series`, `_fit_from_series`, `_regime_at` unchanged this task (they do not call `expert.signal`; `build_moe_report` calls the above with funding/oi defaulting None).

- [ ] **Step 5: Grep for any other caller of the old signature**

Run: `grep -rn "\.signal(" src/moonface/signal/engine/moe/ tests/test_moe_*.py`
Expected: the only `expert.signal(ctx)` call site in `src/` is inside `_raw_series`; the only test call sites are the two updated files. If any other call passes `(window, index, cfg)` positionally, update it to build an `ExpertContext`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_moe_orthogonal_experts.py tests/test_moe_experts.py tests/test_moe_report.py tests/test_moe_null_calibration.py -v`
Expected: PASS (orthogonal + experts green; report + null unchanged and still green because funding/oi default None → orthogonal experts no-fire).

- [ ] **Step 7: Commit**

```bash
git add src/moonface/signal/engine/moe/experts.py src/moonface/signal/engine/moe/evaluate_moe.py tests/test_moe_orthogonal_experts.py tests/test_moe_experts.py
git commit -m "feat(moe): ExpertContext + funding/OI experts; thread orthogonal data to _raw_series"
```

---

### Task 3: Bundle-input `build_moe_report` + record trial identity

**Files:**
- Modify: `src/moonface/signal/engine/moe/evaluate_moe.py`
- Test: `tests/test_moe_report.py` (bundle inputs)
- Test: `tests/test_moe_null_calibration.py` (5-expert non-vacuous Gate-0)

**Interfaces:**
- Consumes: `DataBundle` (`from moonface.foundation.bundle import DataBundle`); `default_experts`, `ORTHO_CONSTANTS` from experts; `identity_hash` from config_moe; the Task-2 funding/oi passthroughs.
- Produces: `build_moe_report(btc: DataBundle, eth: DataBundle, sol: DataBundle, cfg_v3, cfg_v22, cfg_moe, warmup, lookback=LOOKBACK, experts=None) -> dict`. Default `experts = default_experts()`. Report gains keys `"experts"` (list of names), `"identity_hash"`, `"ortho_constants"`. When a bundle's `funding`/`feature` is `None`, orthogonal experts no-fire.

- [ ] **Step 1: Write the failing test**

Replace `tests/test_moe_report.py` body (keep its existing `_make_candles` DAY_MS helper — it spans the split windows) so inputs are `DataBundle`s with synthetic funding/OI:

```python
# tests/test_moe_report.py
import random

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.signal.engine.config import EngineConfig
from moonface.signal.engine.moe.config_moe import MoeConfig
from moonface.signal.engine.moe.evaluate_moe import build_moe_report
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.evaluate import SPAN_START_TS_MS

DAY_MS = 86_400_000


def _make_candles(n: int, seed: int = 1729) -> list[Candle]:
    rng = random.Random(seed)
    candles, price = [], 100.0
    for i in range(n):
        drift = 0.0015 if (i // 80) % 2 == 0 else -0.0012
        noise = rng.uniform(-0.01, 0.01)
        open_ = price
        close = max(1.0, price * (1.0 + drift + noise))
        high = max(open_, close) * (1.0 + rng.uniform(0.0, 0.006))
        low = min(open_, close) * (1.0 - rng.uniform(0.0, 0.006))
        candles.append(Candle(SPAN_START_TS_MS + i * DAY_MS, open_, high, low, close,
                              1000.0 + rng.uniform(-200.0, 200.0)))
        price = close
    return candles


def _bundle(candles, seed=0):
    rng = random.Random(seed)
    funding = [rng.uniform(-0.02, 0.02) for _ in candles]
    oi = []
    v = 1_000_000.0
    for _ in candles:
        v = max(1.0, v * (1.0 + rng.uniform(-0.05, 0.05)))
        oi.append(v)
    return DataBundle(candles=candles, funding=funding, feature=oi)


VALID = {
    "GATE0_FAILED_HALT", "POWER_BUDGET_REFUSED", "CLOSED_NEGATIVE_VALIDATION",
    "CLOSED_NEGATIVE_SEALED_BTC", "CLOSED_NEGATIVE_TRANSFER",
    "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
}


def test_report_records_identity_and_experts():
    btc, eth, sol = _make_candles(2500, 1), _make_candles(2500, 2), _make_candles(2500, 3)
    report = build_moe_report(
        _bundle(btc, 1), _bundle(eth, 2), _bundle(sol, 3),
        EngineConfigV3(), EngineConfig(), MoeConfig(), warmup=400, lookback=400)
    assert report["experts"] == ["BREAKOUT", "PULLBACK", "REVERSION", "FUNDING", "OI"]
    assert len(report["identity_hash"]) == 64
    assert report["ortho_constants"] == {"FUNDING_CAP": 0.01, "OI_LOOKBACK": 24}
    assert report["verdict"] in VALID
    if report["verdict"] in {"GATE0_FAILED_HALT", "POWER_BUDGET_REFUSED", "CLOSED_NEGATIVE_VALIDATION"}:
        assert report["gate2"] is None


def test_synthetic_noise_does_not_pass():
    btc = _make_candles(2500, 7)
    report = build_moe_report(
        _bundle(btc, 7), _bundle(btc, 8), _bundle(btc, 9),
        EngineConfigV3(), EngineConfig(), MoeConfig(), warmup=400, lookback=400)
    assert report["verdict"] != "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"


def test_ortho_none_bundle_reduces_to_price_only():
    # funding/feature None -> orthogonal experts no-fire; still a valid verdict
    btc = _make_candles(2500, 4)
    report = build_moe_report(
        DataBundle(candles=btc), DataBundle(candles=btc), DataBundle(candles=btc),
        EngineConfigV3(), EngineConfig(), MoeConfig(), warmup=400, lookback=400)
    assert report["verdict"] in VALID
```

Extend `tests/test_moe_null_calibration.py` with a 5-expert non-vacuous check (keep its existing `_make_candles`; attach synthetic funding/OI):

```python
# add to tests/test_moe_null_calibration.py
import random as _random

from moonface.signal.engine.moe.experts import default_experts
from moonface.signal.engine.moe.evaluate_moe import null_calibration


def test_gate0_negative_and_nonvacuous_with_orthogonal_experts():
    candles = _make_candles(3000)
    rng = _random.Random(11)
    funding = [rng.uniform(-0.02, 0.02) for _ in candles]
    oi, v = [], 1_000_000.0
    for _ in candles:
        v = max(1.0, v * (1.0 + rng.uniform(-0.05, 0.05)))
        oi.append(v)
    result = null_calibration(
        candles, EngineConfigV3(), EngineConfig(), default_experts(), MoeConfig(),
        funding=funding, oi=oi)
    assert result["passed_negative"] is True, result
    # non-vacuous: at least one null run actually fired trades (guards a tautology pass)
    assert any(run["n"] > 0 for run in result["runs"].values()), result
```

> Note: `test_moe_null_calibration.py` already imports `EngineConfig`, `EngineConfigV3`, `MoeConfig`, and defines `_make_candles`; reuse them. Only add the imports shown.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_moe_report.py tests/test_moe_null_calibration.py -v`
Expected: FAIL — `build_moe_report` rejects `DataBundle` (treats it as candles) / missing `experts`/`identity_hash` keys.

- [ ] **Step 3: Update `build_moe_report` in `evaluate_moe.py`**

Add imports (top of file):

```python
from moonface.foundation.bundle import DataBundle  # noqa: F401  (type of inputs)
from moonface.signal.engine.moe.config_moe import identity_hash, moe_hash
from moonface.signal.engine.moe.experts import ORTHO_CONSTANTS, default_experts
```

Rewrite `build_moe_report` (unpack bundles; default to `default_experts()`; thread funding/oi; record identity). Replace the `if experts is None:` block and the calls that follow:

```python
def build_moe_report(btc, eth, sol, cfg_v3, cfg_v22, cfg_moe, warmup,
                     lookback=LOOKBACK, experts=None):
    if experts is None:
        experts = default_experts()

    btc_c, btc_f, btc_oi = btc.candles, btc.funding, btc.feature
    eth_c, eth_f, eth_oi = eth.candles, eth.funding, eth.feature
    sol_c, sol_f, sol_oi = sol.candles, sol.funding, sol.feature
    names = [expert.name for expert in experts]

    gate0 = null_calibration(btc_c, cfg_v3, cfg_v22, experts, cfg_moe,
                             funding=btc_f, oi=btc_oi)

    train_samples, train_series = build_fit_panel(
        btc_c, cfg_v3, cfg_v22, experts, lookback, end_ts_ms=TRAIN_END_TS_MS,
        funding=btc_f, oi=btc_oi)
    normalizer = Normalizer.fit(train_series, cfg_moe)
    W = fit_weights(train_samples, names, cfg_moe, n_train_trades=len(train_samples))
    eff = p_eff(W)
    allowed = allowed_p_eff(len(train_samples), cfg_moe.m_per_weight)
    power_ok = check_power_budget(len(train_samples), eff, cfg_moe.m_per_weight)

    report = {
        "moe_hash": moe_hash(cfg_moe),
        "identity_hash": identity_hash(cfg_moe, names, ORTHO_CONSTANTS),
        "experts": names,
        "ortho_constants": ORTHO_CONSTANTS,
        "gate0": gate0,
        "power": {"n_train": len(train_samples), "p_eff": eff,
                  "allowed": allowed, "passed": power_ok},
        "fitted": {"p_eff": eff, "matrix": {
            regime.value: {name: round(weight, 4) for name, weight in row.items() if weight > 0.0}
            for regime, row in W.items()}},
        "gate1": None, "gate2": None, "gate3": None,
    }

    if not gate0["passed_negative"]:
        report["verdict"] = "GATE0_FAILED_HALT"
        return report
    if not power_ok:
        report["verdict"] = "POWER_BUDGET_REFUSED"
        return report

    btc_pairs = _pairs_for_asset(btc_c, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe,
                                 lookback, funding=btc_f, oi=btc_oi)
    val_pairs = split_pairs_by_window(btc_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS)
    base_pairs = v22_pairs(btc_c, cfg_v22, warmup)
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

    eth_pairs = split_pairs_by_window(
        _pairs_for_asset(eth_c, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback,
                         funding=eth_f, oi=eth_oi),
        SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)
    sol_pairs = split_pairs_by_window(
        _pairs_for_asset(sol_c, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback,
                         funding=sol_f, oi=sol_oi),
        SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS)
    gate3 = gate3_transfer(eth_pairs, sol_pairs)
    report["gate3"] = gate3
    report["verdict"] = ("ALL_GATES_PASSED_HUMAN_DECISION_PENDING" if gate3["passed"]
                         else "CLOSED_NEGATIVE_TRANSFER")
    return report
```

> Delete the now-duplicate `moe_hash` import if it exists on its own line (it is re-imported above with `identity_hash`). Keep only one import of `moe_hash`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_moe_report.py tests/test_moe_null_calibration.py -v`
Expected: PASS. If `test_gate0_negative_and_nonvacuous...` fails with `passed_negative False`, the combiner finds edge on nulled orthogonal experts — tighten gates, never weaken the test. If it fails the non-vacuous assertion (`n>0`), the synthetic funding/OI is too flat — increase its variance, do not drop the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/moe/evaluate_moe.py tests/test_moe_report.py tests/test_moe_null_calibration.py
git commit -m "feat(moe): bundle-input build_moe_report with default 5-expert set + identity record"
```

---

### Task 4: CLI — orthogonal data + `--experts`

**Files:**
- Modify: `tools/moe_evaluate.py`
- Test: `tests/test_moe_cli.py`

**Interfaces:**
- Consumes: `default_experts`, `mechanism_experts`, `orthogonal_experts`; `ASSETS`; `load_bundle`; the Task-3 `build_moe_report`.
- Produces: `--experts {price,ortho,all}` (default `all`); MoE asset dicts carry `funding_symbol` (= perp symbol) and `metrics_field="sum_open_interest"`; `run()` passes full `DataBundle`s (not `.candles`) to `build_moe_report`.

- [ ] **Step 1: Write the failing test**

Extend `tests/test_moe_cli.py`:

```python
# add to tests/test_moe_cli.py
from tools.moe_evaluate import _moe_asset, build_parser


def test_experts_flag_parses():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1", "--experts", "price"])
    assert args.experts == "price"
    default = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1"])
    assert default.experts == "all"


def test_moe_asset_carries_funding_and_oi():
    a = _moe_asset("BTC")
    assert a["funding_symbol"] == a["symbol"]
    assert a["metrics_field"] == "sum_open_interest"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_moe_cli.py -v`
Expected: FAIL with `ImportError: cannot import name '_moe_asset'` / missing `--experts`.

- [ ] **Step 3: Update `tools/moe_evaluate.py`**

Change the experts import and add the helpers/flag/bundle-pass:

```python
from moonface.signal.engine.moe.experts import (
    default_experts,
    mechanism_experts,
    orthogonal_experts,
)
```

Add near the top (after imports):

```python
_EXPERT_SETS = {
    "price": mechanism_experts,
    "ortho": orthogonal_experts,
    "all": default_experts,
}


def _moe_asset(key: str) -> dict:
    asset = dict(ASSETS[key])
    asset["funding_symbol"] = asset["symbol"]
    asset["metrics_field"] = "sum_open_interest"
    return asset
```

In `build_parser`, add before `--out`:

```python
    parser.add_argument("--experts", choices=["price", "ortho", "all"], default="all",
                        help="expert set (frozen into identity_hash)")
```

Rewrite `run()`'s body to load bundles and select experts:

```python
def run(argv: list[str] | None = None, loaders: dict | None = None) -> int:
    args = build_parser().parse_args(argv)
    load = loaders or {key: load_bundle for key in ASSETS}
    cfg_v22 = load_engine_config(args.v22_engine)
    cfg_v3 = EngineConfigV3()
    cfg_moe = MoeConfig(q_confluence=args.q_confluence)
    experts = _EXPERT_SETS[args.experts]()

    def bundle(key: str):
        return load[key](_moe_asset(key), args.start_ms, args.end_ms, args.cache_dir)

    report = build_moe_report(
        bundle("BTC"), bundle("ETH"), bundle("SOL"),
        cfg_v3, cfg_v22, cfg_moe, args.warmup, args.lookback, experts=experts)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_moe_cli.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add tools/moe_evaluate.py tests/test_moe_cli.py
git commit -m "feat(moe): CLI loads funding+OI bundles and selects expert set via --experts"
```

---

### Task 5: Pre-registration document (before the run)

**Files:**
- Create: `experiments/engine/MOE_ORTHO_REGISTRATION.md`

**Interfaces:**
- Consumes: `identity_hash` (to freeze the trial identity); the frozen expert set and constants.
- Produces: a committed pre-registration. No code.

- [ ] **Step 1: Compute the frozen identity to embed**

Run:

```bash
.venv/bin/python -c "
from moonface.signal.engine.moe.config_moe import MoeConfig, identity_hash
from moonface.signal.engine.moe.experts import ORTHO_CONSTANTS, default_experts
names=[e.name for e in default_experts()]
print('experts:', names)
print('identity_hash(q=1):', identity_hash(MoeConfig(q_confluence=1), names, ORTHO_CONSTANTS))
"
```

Record the printed `identity_hash` in the doc below.

- [ ] **Step 2: Write `experiments/engine/MOE_ORTHO_REGISTRATION.md`**

```markdown
# Regime-MoE — Orthogonal-Expert Registration (Trial 3)

**Registered:** <DATE> (BEFORE any evaluation of this config).
**Expert set (frozen):** BREAKOUT, PULLBACK, REVERSION, FUNDING, OI.
**Frozen constants:** FUNDING_CAP=0.01, OI_LOOKBACK=24.
**Config:** MoeConfig(q_confluence=1); all other fields default.
**Frozen identity_hash:** <PASTE from Step 1>

## Lineage
Trials 1 (q=2, no-fire) and 2 (q=1, fires n=353 but flat, CI straddles 0) both
CLOSED_NEGATIVE_VALIDATION; sealed UNSPENT; config-tuning line closed. This trial adds two
orthogonal (non-price) experts. q_confluence=1 is chosen so the new experts are actually
tested (trial 2 proved q=2 risks a structural no-fire).

## Hypothesis
Regime-conditioned weighting of funding (crowd-fade) and OI (confirmation) contributes edge
the price mechanisms lacked. **Honest prior: negative** (OI standalone dead, funding-fade
transfer dead). The open question is regime-conditioned combination.

## Trial accounting
Trial 3 of <=EFFECTIVE_TRIALS=12; DSR deflates with n_trials=12.

## Gate order / sealed-once (unchanged)
GATE0_FAILED_HALT -> POWER_BUDGET_REFUSED -> CLOSED_NEGATIVE_VALIDATION ->
CLOSED_NEGATIVE_SEALED_BTC -> CLOSED_NEGATIVE_TRANSFER -> ALL_GATES_PASSED_HUMAN_DECISION_PENDING.
Gate-0 must pass first; sealed opens ONLY if Gate-0+power+Gate-1 pass; sealed spent ONCE
(currently UNSPENT; this config CAN reach it).

## Command
.venv/bin/python -m tools.moe_evaluate --start-ms 1577836800000 --end-ms 1782316800000 \
  --q-confluence 1 --experts all --out experiments/engine/moe_eval_ortho.json

## Kill rule / terminal
Expected CLOSED_NEGATIVE_VALIDATION or _SEALED_BTC. Only ALL_GATES_PASSED warrants (human)
deliberation; never auto-promote. A negative closes the free-data orthogonal-expert line.
```

Replace `<DATE>` and `<PASTE...>` with the real values before committing.

- [ ] **Step 3: Commit (before running the evaluation)**

```bash
git add experiments/engine/MOE_ORTHO_REGISTRATION.md
git commit -m "spec(regime_moe): register orthogonal-expert trial 3 (identity_hash frozen)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| §2.1 FUNDING expert | Task 2 |
| §2.2 OI expert | Task 2 |
| §2.3 frozen constants | Task 2 |
| §3 ExpertContext + protocol | Task 2 |
| §4 data plumbing (bundle input, thread funding/OI) | Tasks 2 (internals) + 3 (build_moe_report) |
| §5 identity_hash (registration integrity) | Task 1 (fn) + Task 3 (record) |
| §6 anti-artifact protocol (Gate-0 first, power, sealed-once, trial 3/12) | Task 3 (unchanged gates) + Task 5 (accounting) |
| §7 testing | Tasks 1-4 tests |
| §8 OI coverage / no-lookahead | Task 2 (None→no-fire, causal slicing) |
| §9 file-change summary | all tasks |
| §10 kill rule | Task 5 |

**2. Placeholder scan:** No "TBD"/"TODO". The registration doc's `<DATE>`/`<PASTE>` are explicit fill-ins with a compute step (Task 5 Step 1) — not placeholders in code.

**3. Type consistency:** `ExpertContext(window,index,cfg,funding,oi)` produced in Task 2, consumed only in `_raw_series`. `RawSignal(direction,magnitude)` unchanged. `_raw_series(...,funding,oi)` and its 4 callers threaded in Task 2; `build_moe_report` consumes `DataBundle.candles/.funding/.feature` in Task 3. `identity_hash(cfg, names, ortho_constants)` defined in Task 1, called in Task 3 with `ORTHO_CONSTANTS` from experts. `default_experts()` names `[BREAKOUT,PULLBACK,REVERSION,FUNDING,OI]` consistent across Tasks 2/3/4.

---

## Known Risks / Notes for the Implementer

- **`expert.signal` has ONE call site** (`_raw_series`). Grep `\.signal(` before/after Task 2 to confirm no other positional caller survives.
- **OI coverage:** `sum_open_interest` starts ~2020-09; the ~11.5% head-gap clears the 80% `_check_coverage` floor, so `load_bundle` will not reject. Early bars have `oi=None` → OI expert no-fires (already handled).
- **Suite stays green after each task:** Task 2 keeps `build_moe_report` on the old (candle-list) path with funding/oi defaulting None, so nothing breaks until Task 3 flips it to bundles and rewrites `test_moe_report.py` in the same commit.
- **Gate-0 is the whole point.** If `passed_negative` is False on the 5-expert nulls, tighten gates — never weaken the null test. The expected end verdict is still `CLOSED_NEGATIVE_VALIDATION` or `_SEALED_BTC`; a certified negative is the deliverable working.
```
