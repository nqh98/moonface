# Regime-Mechanism Engine (v3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new live trading engine (`v3`) in which a market regime selects exactly one specialist mechanism, that mechanism's trigger is the sole decision to trade, and a post-selection quality score only sizes the position — never sums weak confirmations into a trade.

**Architecture:** New isolated subpackage `src/moonface/signal/engine/v3/`. A pure regime classifier (`trend/range × volatility`) feeds a frozen `regime → one mechanism` matrix; a small fresh mechanism library (`BREAKOUT`, `PULLBACK`, `REVERSION`) each expose a single `evaluate` returning direction + quality; sizing is a monotone quality→fraction curve with a zero-floor veto. `decide_v3` orchestrates classify → select → trigger → size. v2.2 files are never touched.

**Tech Stack:** Python 3.11+, stdlib only (no numpy). Tests via pytest in `tests/`. Spec: `docs/research-log/specs/2026-07-06-regime-mechanism-engine-v3-design.md`.

## Global Constraints

- **v2.2 stays byte-frozen.** No edits to any existing file under `src/moonface/signal/engine/`. Everything new lives under the new `v3/` subpackage. Existing tests must stay green.
- **The core invariant (spec §2):** a trade exists iff the single regime-selected mechanism's trigger fires; the quality score may only scale size within `[0, max_fraction]` and veto degenerate cases (`quality < q_floor → size 0`). No score ever creates a trade; no second mechanism is consulted on a bar. Task 10 tests this directly.
- **Stdlib only.** No numpy. Reuse `moonface.foundation.risk.atr`; implement other indicators in `v3/indicators.py`.
- **Run commands:** `.venv/bin/pytest …` and `.venv/bin/python …`. Never bare `python`, never `rtk python`.
- **Git:** no AI attribution trailers. Never chain `git add && git commit` blindly — stage, check `git diff --cached --stat`, then commit. `docs/` is globally gitignored; the spec/plan are already committed (`git add -f` was used) — do not re-add them in feature commits.
- **Sizing carries no regime term.** Regime's only job is selection; sizing is purely quality-driven and mechanism-owned.
- **TDD:** every task writes its failing test first, verifies failure, implements, verifies pass, commits.

---

### Task 1: v3 config, version, and frozen hash

**Files:**
- Create: `src/moonface/signal/engine/v3/__init__.py`
- Create: `src/moonface/signal/engine/v3/config_v3.py`
- Test: `tests/test_v3_config.py`

**Interfaces:**
- Produces: `ENGINE_V3_VERSION: str`, `EngineConfigV3` (frozen dataclass with every numeric parameter below), `load_engine_config_v3(path) -> EngineConfigV3`, `engine_hash_v3(cfg: EngineConfigV3) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v3_config.py
"""v3 engine config: frozen defaults, disabled-by-default, stable hash."""
from moonface.signal.engine.v3.config_v3 import (
    ENGINE_V3_VERSION,
    EngineConfigV3,
    engine_hash_v3,
)


def test_defaults_are_disabled_and_versioned():
    cfg = EngineConfigV3()
    assert cfg.enabled is False
    assert ENGINE_V3_VERSION == "v3"
    assert cfg.base_fraction == 0.005 and cfg.max_fraction == 0.02


def test_hash_is_stable_and_ignores_enabled():
    a = EngineConfigV3()
    b = EngineConfigV3(enabled=True)
    assert engine_hash_v3(a) == engine_hash_v3(b)
    assert len(engine_hash_v3(a)) == 64


def test_hash_changes_when_a_frozen_param_changes():
    base = EngineConfigV3()
    moved = EngineConfigV3(adx_trend=30.0)
    assert engine_hash_v3(base) != engine_hash_v3(moved)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_v3_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/__init__.py
"""Regime-mechanism engine (v3). Regime selects one specialist mechanism; the
mechanism trigger is the sole trade decision; quality only sizes. v2.2 is not
imported or modified from here."""
```

```python
# src/moonface/signal/engine/v3/config_v3.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

ENGINE_V3_VERSION = "v3"


def _default_asset() -> dict:
    return {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"}


@dataclass(frozen=True)
class EngineConfigV3:
    """All v3 parameters. Absent/invalid config file -> these defaults, which
    are DISABLED (enabled=False)."""

    enabled: bool = False
    asset: dict = field(default_factory=_default_asset)
    lookback_bars: int = 6000
    # --- regime classifier ---
    adx_period: int = 14
    adx_trend: float = 25.0
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    vol_baseline: int = 100
    vol_quiet_ratio: float = 0.7
    vol_high_ratio: float = 1.5
    vol_extreme_ratio: float = 2.5
    # --- BREAKOUT ---
    breakout_n: int = 20
    roc_n: int = 10
    ext_scale: float = 1.0
    roc_scale: float = 0.05
    # --- PULLBACK ---
    pullback_ema: int = 20
    pullback_tol: float = 0.003
    adx_scale: float = 40.0
    # --- REVERSION ---
    band_period: int = 20
    band_k: float = 2.0
    rsi_period: int = 14
    stretch_scale: float = 1.5
    # --- sizing (per-mechanism quality floor + shared fraction bounds) ---
    q_floor_breakout: float = 0.20
    q_floor_pullback: float = 0.25
    q_floor_reversion: float = 0.30
    base_fraction: float = 0.005
    max_fraction: float = 0.02


_CONFIG_FIELDS = set(EngineConfigV3.__dataclass_fields__.keys())

# The regime->mechanism table is part of the frozen identity of the engine; it
# is hashed as text so any matrix edit forces a new hash. Kept here (not
# imported from matrix.py) to avoid a config->matrix import cycle; Task 8 adds a
# test asserting the two tables agree.
_FROZEN_MATRIX_TEXT = (
    "TRENDING_UP|QUIET=PULLBACK;TRENDING_UP|NORMAL=BREAKOUT;"
    "TRENDING_UP|HIGH=BREAKOUT;RANGING|QUIET=REVERSION;"
    "RANGING|NORMAL=REVERSION;RANGING|HIGH=None;"
    "TRENDING_DOWN|QUIET=PULLBACK;TRENDING_DOWN|NORMAL=BREAKOUT;"
    "TRENDING_DOWN|HIGH=BREAKOUT"
)


def load_engine_config_v3(path) -> EngineConfigV3:
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            return EngineConfigV3()
        overrides = {k: v for k, v in raw.items() if k in _CONFIG_FIELDS}
        return EngineConfigV3(**overrides)
    except (OSError, ValueError, TypeError):
        return EngineConfigV3()


def engine_hash_v3(cfg: EngineConfigV3) -> str:
    payload = {
        k: getattr(cfg, k) for k in sorted(_CONFIG_FIELDS) if k != "enabled"
    }
    payload["__matrix__"] = _FROZEN_MATRIX_TEXT
    payload["__engine_version__"] = ENGINE_V3_VERSION
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_v3_config.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/__init__.py src/moonface/signal/engine/v3/config_v3.py tests/test_v3_config.py
git diff --cached --stat
git commit -m "feat(v3): engine config, version, and frozen hash"
```

---

### Task 2: Indicators (stdlib)

**Files:**
- Create: `src/moonface/signal/engine/v3/indicators.py`
- Test: `tests/helpers_v3.py`
- Test: `tests/test_v3_indicators.py`

**Interfaces:**
- Consumes: `Candle` from `moonface.foundation.models`; `atr` from `moonface.foundation.risk`.
- Produces: `ema(values, period) -> float`, `roc(values, n) -> float`, `rsi(closes, period) -> float`, `adx(candles, period) -> float`, `sma(values, period) -> float`, `stdev(values, period) -> float`, `donchian_high(candles, n) -> float`, `donchian_low(candles, n) -> float`, `vol_ratio(candles, atr_period, baseline) -> float`. Plus test helpers `H`, `c(i, o, h, l, cl)`, `uptrend(n, ...)`, `downtrend(n, ...)`, `flat_range(n, ...)`.

- [ ] **Step 1: Write the shared test helper**

```python
# tests/helpers_v3.py
"""Hermetic synthetic candle builders for the v3 engine tests."""
from __future__ import annotations

import math

from moonface.foundation.models import Candle

H = 3_600_000


def c(i: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(i * H, o, h, l, cl, 10.0)


def uptrend(n: int, step: float = 1.0, start: float = 100.0,
            wick: float = 0.2) -> list[Candle]:
    out: list[Candle] = []
    p = start
    for i in range(n):
        o = p
        cl = p + step
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
        p = cl
    return out


def downtrend(n: int, step: float = 1.0, start: float = 500.0,
              wick: float = 0.2) -> list[Candle]:
    out: list[Candle] = []
    p = start
    for i in range(n):
        o = p
        cl = p - step
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
        p = cl
    return out


def flat_range(n: int, mid: float = 100.0, amp: float = 2.0,
               period: int = 8, wick: float = 0.3) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        cl = mid + amp * math.sin(2 * math.pi * i / period)
        o = mid + amp * math.sin(2 * math.pi * (i - 1) / period)
        out.append(c(i, o, max(o, cl) + wick, min(o, cl) - wick, cl))
    return out
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_v3_indicators.py
"""Stdlib indicator helpers used by the regime classifier and mechanisms."""
from moonface.signal.engine.v3.indicators import (
    adx,
    donchian_high,
    donchian_low,
    ema,
    roc,
    rsi,
    sma,
    stdev,
    vol_ratio,
)

from tests.helpers_v3 import flat_range, uptrend


def test_ema_tracks_toward_latest():
    assert abs(ema([10.0] * 20, 10) - 10.0) < 1e-9
    assert ema([0.0] * 10 + [10.0] * 10, 5) > 5.0


def test_roc_signs_with_direction():
    assert roc([100.0, 101.0, 102.0, 110.0], 3) > 0
    assert roc([110.0, 105.0, 100.0], 2) < 0
    assert roc([100.0], 5) == 0.0


def test_sma_and_stdev():
    assert sma([1.0, 2.0, 3.0, 4.0], 4) == 2.5
    assert abs(stdev([2.0, 2.0, 2.0], 3)) < 1e-9
    assert stdev([1.0, 3.0], 2) > 0


def test_donchian_uses_prior_bars_only():
    up = uptrend(30)
    # current close is a fresh high above the prior-20 channel
    assert up[-1].close > donchian_high(up, 20)
    assert donchian_low(up, 20) < up[-1].close


def test_adx_high_in_trend_low_in_range():
    assert adx(uptrend(60), 14) > 25.0
    assert adx(flat_range(60), 14) < 25.0


def test_rsi_bounds_and_direction():
    assert rsi([float(x) for x in range(1, 40)], 14) > 70.0
    assert rsi([float(x) for x in range(40, 1, -1)], 14) < 30.0


def test_vol_ratio_positive():
    assert vol_ratio(uptrend(120), 14, 100) > 0.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_indicators.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.indicators'`

- [ ] **Step 4: Write the implementation**

```python
# src/moonface/signal/engine/v3/indicators.py
from __future__ import annotations

from moonface.foundation.models import Candle
from moonface.foundation.risk import atr


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2.0 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def roc(values: list[float], n: int) -> float:
    if len(values) <= n or values[-1 - n] == 0:
        return 0.0
    return (values[-1] - values[-1 - n]) / values[-1 - n]


def sma(values: list[float], period: int) -> float:
    window = values[-period:]
    return sum(window) / len(window) if window else 0.0


def stdev(values: list[float], period: int) -> float:
    window = values[-period:]
    if len(window) < 2:
        return 0.0
    m = sum(window) / len(window)
    return (sum((v - m) ** 2 for v in window) / len(window)) ** 0.5


def donchian_high(candles: list[Candle], n: int) -> float:
    prior = candles[-(n + 1):-1] if len(candles) > n else candles[:-1]
    return max((x.high for x in prior), default=candles[-1].high)


def donchian_low(candles: list[Candle], n: int) -> float:
    prior = candles[-(n + 1):-1] if len(candles) > n else candles[:-1]
    return min((x.low for x in prior), default=candles[-1].low)


def _wilder(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    acc = sum(values[:period])
    out = [acc]
    for v in values[period:]:
        acc = acc - acc / period + v
        out.append(acc)
    return out


def adx(candles: list[Candle], period: int) -> float:
    if len(candles) < 2 * period + 1:
        return 0.0
    trs: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for i in range(1, len(candles)):
        h, l = candles[i].high, candles[i].low
        ph, pl, pc = candles[i - 1].high, candles[i - 1].low, candles[i - 1].close
        up = h - ph
        down = pl - l
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    tr_s = _wilder(trs, period)
    pdm_s = _wilder(plus_dm, period)
    mdm_s = _wilder(minus_dm, period)
    dx: list[float] = []
    for tr_, pdm_, mdm_ in zip(tr_s, pdm_s, mdm_s):
        if tr_ == 0:
            continue
        pdi = 100.0 * pdm_ / tr_
        mdi = 100.0 * mdm_ / tr_
        denom = pdi + mdi
        if denom == 0:
            continue
        dx.append(100.0 * abs(pdi - mdi) / denom)
    if len(dx) < period:
        return 0.0
    val = sum(dx[:period]) / period
    for d in dx[period:]:
        val = (val * (period - 1) + d) / period
    return val


def rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += ch if ch > 0 else 0.0
        losses += -ch if ch < 0 else 0.0
    ag = gains / period
    al = losses / period
    for i in range(period + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + (ch if ch > 0 else 0.0)) / period
        al = (al * (period - 1) + (-ch if ch < 0 else 0.0)) / period
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def vol_ratio(candles: list[Candle], atr_period: int, baseline: int) -> float:
    """Current short-window ATR relative to a longer baseline ATR."""
    long_atr = atr(candles, baseline)
    if long_atr <= 0:
        return 0.0
    return atr(candles, atr_period) / long_atr
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_indicators.py -q`
Expected: 7 passed. If `test_adx_high_in_trend_low_in_range` is borderline, raise the series length in the helper call (e.g. `uptrend(80)`) — do NOT lower `ADX_TREND`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/signal/engine/v3/indicators.py tests/helpers_v3.py tests/test_v3_indicators.py
git diff --cached --stat
git commit -m "feat(v3): stdlib indicators + hermetic candle helpers"
```

---

### Task 3: Regime classifier

**Files:**
- Create: `src/moonface/signal/engine/v3/regime.py`
- Test: `tests/test_v3_regime.py`

**Interfaces:**
- Consumes: indicators from Task 2; `EngineConfigV3`.
- Produces: `DirState` (Enum: `TRENDING_UP`, `RANGING`, `TRENDING_DOWN`), `VolState` (Enum: `QUIET`, `NORMAL`, `HIGH`, `EXTREME`), `Regime` (frozen dataclass `dir_state: DirState`, `vol_state: VolState`), `classify_dir(candles, cfg) -> DirState`, `classify_vol(candles, cfg) -> VolState`, `classify_regime(candles, cfg) -> Regime`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_regime.py
"""Regime classifier: trend/range x volatility, conservative RANGING default."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.regime import (
    DirState,
    VolState,
    classify_dir,
    classify_regime,
    classify_vol,
)

from tests.helpers_v3 import c, downtrend, flat_range, uptrend

CFG = EngineConfigV3()


def test_dir_state_up_down_range():
    assert classify_dir(uptrend(80), CFG) == DirState.TRENDING_UP
    assert classify_dir(downtrend(80), CFG) == DirState.TRENDING_DOWN
    assert classify_dir(flat_range(80), CFG) == DirState.RANGING


def test_vol_state_extreme_from_recent_spike():
    quiet = uptrend(120, step=0.2, wick=0.05)
    spiked = quiet + [c(120 + j, 200.0, 260.0, 195.0, 255.0) for j in range(3)]
    assert classify_vol(spiked, CFG) == VolState.EXTREME


def test_vol_state_normal_for_steady_series():
    assert classify_vol(uptrend(120), CFG) == VolState.NORMAL


def test_classify_regime_pairs_both_axes():
    reg = classify_regime(uptrend(80), CFG)
    assert reg.dir_state == DirState.TRENDING_UP
    assert reg.vol_state in (VolState.QUIET, VolState.NORMAL, VolState.HIGH)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_regime.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.regime'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/regime.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from moonface.foundation.models import Candle
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.indicators import adx, ema, vol_ratio


class DirState(Enum):
    TRENDING_UP = "TRENDING_UP"
    RANGING = "RANGING"
    TRENDING_DOWN = "TRENDING_DOWN"


class VolState(Enum):
    QUIET = "QUIET"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass(frozen=True)
class Regime:
    dir_state: DirState
    vol_state: VolState


def classify_dir(candles: list[Candle], cfg: EngineConfigV3) -> DirState:
    """Trending iff ADX >= adx_trend; direction from the fast/slow EMA sign.
    Anything not clearly trending is RANGING (we never claim an unmeasured
    trend)."""
    if adx(candles, cfg.adx_period) < cfg.adx_trend:
        return DirState.RANGING
    closes = [x.close for x in candles]
    fast = ema(closes, cfg.ema_fast)
    slow = ema(closes, cfg.ema_slow)
    if fast > slow:
        return DirState.TRENDING_UP
    if fast < slow:
        return DirState.TRENDING_DOWN
    return DirState.RANGING


def classify_vol(candles: list[Candle], cfg: EngineConfigV3) -> VolState:
    ratio = vol_ratio(candles, cfg.atr_period, cfg.vol_baseline)
    if ratio >= cfg.vol_extreme_ratio:
        return VolState.EXTREME
    if ratio >= cfg.vol_high_ratio:
        return VolState.HIGH
    if ratio < cfg.vol_quiet_ratio:
        return VolState.QUIET
    return VolState.NORMAL


def classify_regime(candles: list[Candle], cfg: EngineConfigV3) -> Regime:
    return Regime(classify_dir(candles, cfg), classify_vol(candles, cfg))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_regime.py -q`
Expected: 4 passed. If `test_vol_state_normal_for_steady_series` lands on QUIET/HIGH, the synthetic's short/baseline ATR ratio is off — adjust the helper's `step`/`wick` in the test call, never the config cutpoints.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/regime.py tests/test_v3_regime.py
git diff --cached --stat
git commit -m "feat(v3): trend/range x volatility regime classifier"
```

---

### Task 4: Mechanism base — protocol, signal, bar context

**Files:**
- Create: `src/moonface/signal/engine/v3/mechanisms/__init__.py`
- Create: `src/moonface/signal/engine/v3/mechanisms/base.py`
- Test: `tests/test_v3_mechanism_base.py`

**Interfaces:**
- Consumes: indicators (Task 2); `Regime` (Task 3); `EngineConfigV3`.
- Produces: `MechanismSignal` (frozen dataclass `direction: int`, `quality: float`, `detail: str`), `Mechanism` (Protocol: `name: str`, `evaluate(ctx, regime) -> MechanismSignal`), `BarContext` (frozen dataclass, fields below), `build_context(candles, index, cfg) -> BarContext`, `clip01(x) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_mechanism_base.py
"""Mechanism base: bar context precompute + [0,1] clip."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import (
    build_context,
    clip01,
)

from tests.helpers_v3 import uptrend

CFG = EngineConfigV3()


def test_clip01_bounds():
    assert clip01(-3.0) == 0.0
    assert clip01(0.5) == 0.5
    assert clip01(9.0) == 1.0


def test_build_context_populates_indicators_at_index():
    candles = uptrend(120)
    ctx = build_context(candles, len(candles) - 1, CFG)
    assert ctx.index == len(candles) - 1
    assert ctx.close == candles[-1].close
    assert ctx.atr > 0.0
    assert ctx.donchian_high > 0.0
    assert ctx.band_up >= ctx.band_mid >= ctx.band_lo
    assert 0.0 <= ctx.rsi <= 100.0


def test_build_context_ignores_future_bars():
    candles = uptrend(120)
    early = build_context(candles, 100, CFG)
    assert early.close == candles[100].close
    assert early.donchian_high == build_context(candles[:101], 100, CFG).donchian_high
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_mechanism_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.mechanisms'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/mechanisms/__init__.py
"""Fresh specialist mechanism library for the v3 engine."""
```

```python
# src/moonface/signal/engine/v3/mechanisms/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from moonface.foundation.models import Candle
from moonface.foundation.risk import atr
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.indicators import (
    adx,
    donchian_high,
    donchian_low,
    ema,
    roc,
    rsi,
    sma,
    stdev,
    vol_ratio,
)
from moonface.signal.engine.v3.regime import Regime


def clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


@dataclass(frozen=True)
class MechanismSignal:
    direction: int    # -1, 0, +1 (0 = no trigger this bar)
    quality: float    # [0, 1], meaningful only when direction != 0
    detail: str


@dataclass(frozen=True)
class BarContext:
    index: int
    open: float
    high: float
    low: float
    close: float
    atr: float
    adx: float
    ema_fast: float
    ema_slow: float
    vol_ratio: float
    donchian_high: float
    donchian_low: float
    band_mid: float
    band_up: float
    band_lo: float
    rsi: float
    roc: float


class Mechanism(Protocol):
    name: str

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        ...


def build_context(candles: list[Candle], index: int,
                  cfg: EngineConfigV3) -> BarContext:
    """Precompute every shared indicator once, using only candles[:index+1]."""
    window = candles[: index + 1]
    closes = [x.close for x in window]
    bar = window[-1]
    mid = sma(closes, cfg.band_period)
    sd = stdev(closes, cfg.band_period)
    return BarContext(
        index=index,
        open=bar.open, high=bar.high, low=bar.low, close=bar.close,
        atr=atr(window, cfg.atr_period),
        adx=adx(window, cfg.adx_period),
        ema_fast=ema(closes, cfg.ema_fast),
        ema_slow=ema(closes, cfg.ema_slow),
        vol_ratio=vol_ratio(window, cfg.atr_period, cfg.vol_baseline),
        donchian_high=donchian_high(window, cfg.breakout_n),
        donchian_low=donchian_low(window, cfg.breakout_n),
        band_mid=mid,
        band_up=mid + cfg.band_k * sd,
        band_lo=mid - cfg.band_k * sd,
        rsi=rsi(closes, cfg.rsi_period),
        roc=roc(closes, cfg.roc_n),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_mechanism_base.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/mechanisms/__init__.py src/moonface/signal/engine/v3/mechanisms/base.py tests/test_v3_mechanism_base.py
git diff --cached --stat
git commit -m "feat(v3): mechanism protocol, signal, and bar context"
```

---

### Task 5: BREAKOUT mechanism

**Files:**
- Create: `src/moonface/signal/engine/v3/mechanisms/breakout.py`
- Test: `tests/test_v3_breakout.py`

**Interfaces:**
- Consumes: `BarContext`, `MechanismSignal`, `clip01` (Task 4); `Regime`, `DirState` (Task 3); `EngineConfigV3`.
- Produces: `Breakout` class with `name = "BREAKOUT"` and `evaluate(ctx, regime) -> MechanismSignal`; direction inherited from the regime trend sign; quality blends extension, momentum, and close-in-bar location.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_breakout.py
"""BREAKOUT specialist: channel break in the regime trend direction."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import build_context
from moonface.signal.engine.v3.mechanisms.breakout import Breakout
from moonface.signal.engine.v3.regime import DirState, Regime, VolState

from tests.helpers_v3 import flat_range, uptrend

CFG = EngineConfigV3()
M = Breakout()
UP = Regime(DirState.TRENDING_UP, VolState.NORMAL)
DOWN = Regime(DirState.TRENDING_DOWN, VolState.NORMAL)


def test_fires_long_on_fresh_high_in_uptrend():
    candles = uptrend(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction == 1
    assert 0.0 <= sig.quality <= 1.0


def test_no_trigger_without_breakout():
    candles = flat_range(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction == 0


def test_long_regime_never_fires_short():
    candles = uptrend(60)
    sig = M.evaluate(build_context(candles, len(candles) - 1, CFG), UP)
    assert sig.direction in (0, 1)


def test_quality_rises_with_stronger_thrust():
    weak = uptrend(60, step=0.3)
    strong = uptrend(60, step=3.0)
    qw = M.evaluate(build_context(weak, len(weak) - 1, CFG), UP).quality
    qs = M.evaluate(build_context(strong, len(strong) - 1, CFG), UP).quality
    assert qs >= qw
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_breakout.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.mechanisms.breakout'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/mechanisms/breakout.py
from __future__ import annotations

from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.signal.engine.v3.regime import DirState, Regime


class Breakout:
    name = "BREAKOUT"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        cfg = self.cfg
        d = 1 if regime.dir_state == DirState.TRENDING_UP else (
            -1 if regime.dir_state == DirState.TRENDING_DOWN else 0)
        if d == 0 or ctx.atr <= 0:
            return MechanismSignal(0, 0.0, "no trend direction")
        if d == 1 and ctx.close <= ctx.donchian_high:
            return MechanismSignal(0, 0.0, "no upside break")
        if d == -1 and ctx.close >= ctx.donchian_low:
            return MechanismSignal(0, 0.0, "no downside break")

        edge = ctx.donchian_high if d == 1 else ctx.donchian_low
        extension = clip01(abs(ctx.close - edge) / ctx.atr / cfg.ext_scale)
        momentum = clip01((d * ctx.roc) / cfg.roc_scale)
        span = ctx.high - ctx.low
        if span <= 0:
            location = 0.0
        elif d == 1:
            location = clip01((ctx.close - ctx.low) / span)
        else:
            location = clip01((ctx.high - ctx.close) / span)
        quality = clip01((extension + momentum + location) / 3.0)
        return MechanismSignal(d, quality, f"breakout d={d} q={quality:.3f}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_breakout.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/mechanisms/breakout.py tests/test_v3_breakout.py
git diff --cached --stat
git commit -m "feat(v3): BREAKOUT specialist mechanism"
```

---

### Task 6: PULLBACK mechanism

**Files:**
- Create: `src/moonface/signal/engine/v3/mechanisms/pullback.py`
- Test: `tests/test_v3_pullback.py`

**Interfaces:**
- Consumes: `BarContext`, `MechanismSignal`, `clip01` (Task 4); `Regime`, `DirState` (Task 3); `EngineConfigV3`.
- Produces: `Pullback` class with `name = "PULLBACK"` and `evaluate(ctx, regime) -> MechanismSignal`; direction inherited from the regime trend sign; trigger = tag fast EMA and reclaim; quality blends trend strength, pullback shallowness, reclaim location.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_pullback.py
"""PULLBACK specialist: reclaim of the fast EMA in an established trend."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import BarContext
from moonface.signal.engine.v3.mechanisms.pullback import Pullback
from moonface.signal.engine.v3.regime import DirState, Regime, VolState

CFG = EngineConfigV3()
M = Pullback()
UP = Regime(DirState.TRENDING_UP, VolState.QUIET)
RANGE = Regime(DirState.RANGING, VolState.QUIET)


def _ctx(*, open_, high, low, close, ema_fast, adx=30.0):
    return BarContext(
        index=200, open=open_, high=high, low=low, close=close,
        atr=1.0, adx=adx, ema_fast=ema_fast, ema_slow=ema_fast - 5.0,
        vol_ratio=1.0, donchian_high=high + 5, donchian_low=low - 5,
        band_mid=close, band_up=close + 2, band_lo=close - 2,
        rsi=55.0, roc=0.01)


def test_fires_long_on_ema_tag_and_reclaim():
    # low tags the EMA (100), bar reclaims and closes green above it
    sig = M.evaluate(_ctx(open_=100.5, high=102.0, low=99.9, close=101.5,
                          ema_fast=100.0), UP)
    assert sig.direction == 1
    assert 0.0 <= sig.quality <= 1.0


def test_no_trigger_when_price_never_tags_ema():
    sig = M.evaluate(_ctx(open_=110.0, high=112.0, low=108.0, close=111.0,
                          ema_fast=100.0), UP)
    assert sig.direction == 0


def test_no_trigger_when_not_reclaimed():
    # closes red / below EMA -> no reclaim
    sig = M.evaluate(_ctx(open_=101.0, high=101.2, low=98.0, close=99.0,
                          ema_fast=100.0), UP)
    assert sig.direction == 0


def test_range_regime_gives_no_direction():
    sig = M.evaluate(_ctx(open_=100.5, high=102.0, low=99.9, close=101.5,
                          ema_fast=100.0), RANGE)
    assert sig.direction == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_pullback.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.mechanisms.pullback'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/mechanisms/pullback.py
from __future__ import annotations

from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.signal.engine.v3.regime import DirState, Regime


class Pullback:
    name = "PULLBACK"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        cfg = self.cfg
        d = 1 if regime.dir_state == DirState.TRENDING_UP else (
            -1 if regime.dir_state == DirState.TRENDING_DOWN else 0)
        if d == 0 or ctx.ema_fast <= 0 or ctx.atr <= 0:
            return MechanismSignal(0, 0.0, "no trend direction")

        tol = cfg.pullback_tol
        if d == 1:
            tagged = ctx.low <= ctx.ema_fast * (1 + tol)
            reclaimed = ctx.close > ctx.ema_fast and ctx.close > ctx.open
        else:
            tagged = ctx.high >= ctx.ema_fast * (1 - tol)
            reclaimed = ctx.close < ctx.ema_fast and ctx.close < ctx.open
        if not (tagged and reclaimed):
            return MechanismSignal(0, 0.0, "no ema tag+reclaim")

        strength = clip01(ctx.adx / cfg.adx_scale)
        depth_atr = abs(ctx.close - ctx.ema_fast) / ctx.atr
        shallowness = clip01(1.0 - depth_atr)          # closer to EMA = healthier
        span = ctx.high - ctx.low
        if span <= 0:
            location = 0.0
        elif d == 1:
            location = clip01((ctx.close - ctx.low) / span)
        else:
            location = clip01((ctx.high - ctx.close) / span)
        quality = clip01((strength + shallowness + location) / 3.0)
        return MechanismSignal(d, quality, f"pullback d={d} q={quality:.3f}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_pullback.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/mechanisms/pullback.py tests/test_v3_pullback.py
git diff --cached --stat
git commit -m "feat(v3): PULLBACK specialist mechanism"
```

---

### Task 7: REVERSION mechanism

**Files:**
- Create: `src/moonface/signal/engine/v3/mechanisms/reversion.py`
- Test: `tests/test_v3_reversion.py`

**Interfaces:**
- Consumes: `BarContext`, `MechanismSignal`, `clip01` (Task 4); `Regime` (Task 3); `EngineConfigV3`.
- Produces: `Reversion` class with `name = "REVERSION"` and `evaluate(ctx, regime) -> MechanismSignal`; two-sided (direction from the band hit, ignores regime trend sign); trigger = stretch beyond outer band with rejection; quality blends stretch distance, rejection depth, RSI stretch.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_reversion.py
"""REVERSION specialist: fade a rejected band stretch back to the mean."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import BarContext
from moonface.signal.engine.v3.mechanisms.reversion import Reversion
from moonface.signal.engine.v3.regime import DirState, Regime, VolState

CFG = EngineConfigV3()
M = Reversion()
RANGE = Regime(DirState.RANGING, VolState.NORMAL)


def _ctx(*, high, low, close, band_up, band_lo, mid=100.0, rsi=50.0):
    return BarContext(
        index=200, open=close, high=high, low=low, close=close,
        atr=1.0, adx=15.0, ema_fast=mid, ema_slow=mid, vol_ratio=1.0,
        donchian_high=high + 5, donchian_low=low - 5,
        band_mid=mid, band_up=band_up, band_lo=band_lo, rsi=rsi, roc=0.0)


def test_fades_upper_band_rejection_short():
    sig = M.evaluate(_ctx(high=106.0, low=101.0, close=102.0,
                          band_up=104.0, band_lo=96.0, rsi=78.0), RANGE)
    assert sig.direction == -1
    assert 0.0 <= sig.quality <= 1.0


def test_fades_lower_band_rejection_long():
    sig = M.evaluate(_ctx(high=99.0, low=94.0, close=98.0,
                          band_up=104.0, band_lo=96.0, rsi=22.0), RANGE)
    assert sig.direction == 1


def test_no_trigger_inside_bands():
    sig = M.evaluate(_ctx(high=101.0, low=99.0, close=100.0,
                          band_up=104.0, band_lo=96.0), RANGE)
    assert sig.direction == 0


def test_no_trigger_when_no_rejection():
    # pokes above the band and CLOSES above it -> not rejected
    sig = M.evaluate(_ctx(high=106.0, low=104.5, close=105.5,
                          band_up=104.0, band_lo=96.0), RANGE)
    assert sig.direction == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_reversion.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.mechanisms.reversion'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/mechanisms/reversion.py
from __future__ import annotations

from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.mechanisms.base import (
    BarContext,
    MechanismSignal,
    clip01,
)
from moonface.signal.engine.v3.regime import Regime


class Reversion:
    name = "REVERSION"

    def __init__(self, cfg: EngineConfigV3 | None = None) -> None:
        self.cfg = cfg or EngineConfigV3()

    def evaluate(self, ctx: BarContext, regime: Regime) -> MechanismSignal:
        del regime  # two-sided: direction comes from the band hit, not the regime
        cfg = self.cfg
        if ctx.atr <= 0:
            return MechanismSignal(0, 0.0, "no atr")

        upper_reject = ctx.high >= ctx.band_up and ctx.close < ctx.band_up
        lower_reject = ctx.low <= ctx.band_lo and ctx.close > ctx.band_lo
        if upper_reject:
            d, extreme, rsi_stretch = -1, ctx.high, (ctx.rsi - 50.0) / 50.0
        elif lower_reject:
            d, extreme, rsi_stretch = 1, ctx.low, (50.0 - ctx.rsi) / 50.0
        else:
            return MechanismSignal(0, 0.0, "inside bands or not rejected")

        stretch = clip01(abs(extreme - ctx.band_mid) / ctx.atr / cfg.stretch_scale)
        rejection = clip01(abs(extreme - ctx.close) / ctx.atr)
        rsi_q = clip01(rsi_stretch)
        quality = clip01((stretch + rejection + rsi_q) / 3.0)
        return MechanismSignal(d, quality, f"reversion d={d} q={quality:.3f}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_reversion.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/mechanisms/reversion.py tests/test_v3_reversion.py
git diff --cached --stat
git commit -m "feat(v3): REVERSION specialist mechanism"
```

---

### Task 8: The matrix — registry + selection

**Files:**
- Create: `src/moonface/signal/engine/v3/matrix.py`
- Test: `tests/test_v3_matrix.py`

**Interfaces:**
- Consumes: `DirState`, `VolState`, `Regime` (Task 3); the three mechanism classes (Tasks 5–7); `_FROZEN_MATRIX_TEXT` (Task 1).
- Produces: `MECHANISMS: dict[str, Mechanism]` (name → instance), `REGIME_MECHANISM: dict[tuple[DirState, VolState], str | None]`, `select_mechanism(regime) -> str | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_matrix.py
"""Regime->mechanism matrix: one mechanism per cell, empty cells allowed."""
from moonface.signal.engine.v3.config_v3 import _FROZEN_MATRIX_TEXT
from moonface.signal.engine.v3.matrix import (
    MECHANISMS,
    REGIME_MECHANISM,
    select_mechanism,
)
from moonface.signal.engine.v3.regime import DirState, Regime, VolState


def test_every_cell_maps_and_names_are_known():
    assert len(REGIME_MECHANISM) == 9  # 3 dir x 3 non-extreme vol
    for name in REGIME_MECHANISM.values():
        assert name is None or name in MECHANISMS


def test_selection_matches_table():
    assert select_mechanism(
        Regime(DirState.TRENDING_UP, VolState.QUIET)) == "PULLBACK"
    assert select_mechanism(
        Regime(DirState.TRENDING_UP, VolState.NORMAL)) == "BREAKOUT"
    assert select_mechanism(
        Regime(DirState.RANGING, VolState.NORMAL)) == "REVERSION"
    assert select_mechanism(
        Regime(DirState.RANGING, VolState.HIGH)) is None
    assert select_mechanism(
        Regime(DirState.TRENDING_DOWN, VolState.HIGH)) == "BREAKOUT"


def test_registry_instances_expose_matching_names():
    for name, mech in MECHANISMS.items():
        assert mech.name == name


def test_table_agrees_with_hashed_matrix_text():
    rebuilt = ";".join(
        f"{d.value}|{v.value}="
        f"{REGIME_MECHANISM[(d, v)]}"
        for d in DirState for v in (VolState.QUIET, VolState.NORMAL, VolState.HIGH)
    )
    assert rebuilt == _FROZEN_MATRIX_TEXT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_matrix.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.matrix'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/matrix.py
from __future__ import annotations

from moonface.signal.engine.v3.mechanisms.base import Mechanism
from moonface.signal.engine.v3.mechanisms.breakout import Breakout
from moonface.signal.engine.v3.mechanisms.pullback import Pullback
from moonface.signal.engine.v3.mechanisms.reversion import Reversion
from moonface.signal.engine.v3.regime import DirState, Regime, VolState

MECHANISMS: dict[str, Mechanism] = {
    m.name: m for m in (Breakout(), Pullback(), Reversion())
}

# One mechanism per cell; a None cell means the engine stands flat (the
# structural opposite of manufacturing a trade). EXTREME vol never reaches
# here — decide_v3 short-circuits it to WAIT before selection.
REGIME_MECHANISM: dict[tuple[DirState, VolState], str | None] = {
    (DirState.TRENDING_UP, VolState.QUIET): "PULLBACK",
    (DirState.TRENDING_UP, VolState.NORMAL): "BREAKOUT",
    (DirState.TRENDING_UP, VolState.HIGH): "BREAKOUT",
    (DirState.RANGING, VolState.QUIET): "REVERSION",
    (DirState.RANGING, VolState.NORMAL): "REVERSION",
    (DirState.RANGING, VolState.HIGH): None,
    (DirState.TRENDING_DOWN, VolState.QUIET): "PULLBACK",
    (DirState.TRENDING_DOWN, VolState.NORMAL): "BREAKOUT",
    (DirState.TRENDING_DOWN, VolState.HIGH): "BREAKOUT",
}


def select_mechanism(regime: Regime) -> str | None:
    return REGIME_MECHANISM.get((regime.dir_state, regime.vol_state))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_matrix.py -q`
Expected: 4 passed. `test_table_agrees_with_hashed_matrix_text` guards against the matrix and its hashed text (Task 1) drifting apart.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/matrix.py tests/test_v3_matrix.py
git diff --cached --stat
git commit -m "feat(v3): regime->mechanism matrix and registry"
```

---

### Task 9: Sizing — quality → fraction with zero-floor veto

**Files:**
- Create: `src/moonface/signal/engine/v3/sizing.py`
- Test: `tests/test_v3_sizing.py`

**Interfaces:**
- Consumes: `EngineConfigV3` (Task 1).
- Produces: `q_floor_for(name, cfg) -> float`, `size_from_quality(name, quality, cfg) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_sizing.py
"""Size-only scoring: monotone quality->fraction, zero below the floor."""
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.sizing import q_floor_for, size_from_quality

CFG = EngineConfigV3()


def test_below_floor_is_zero():
    assert size_from_quality("BREAKOUT", 0.19, CFG) == 0.0
    assert size_from_quality("REVERSION", 0.29, CFG) == 0.0


def test_monotone_non_decreasing_in_quality():
    prev = -1.0
    for q in [x / 100 for x in range(20, 101)]:
        f = size_from_quality("BREAKOUT", q, CFG)
        assert f >= prev
        prev = f


def test_caps_at_max_fraction():
    assert size_from_quality("BREAKOUT", 1.0, CFG) == CFG.max_fraction


def test_floor_lookup_per_mechanism():
    assert q_floor_for("BREAKOUT", CFG) == CFG.q_floor_breakout
    assert q_floor_for("PULLBACK", CFG) == CFG.q_floor_pullback
    assert q_floor_for("REVERSION", CFG) == CFG.q_floor_reversion
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_sizing.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.sizing'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/sizing.py
from __future__ import annotations

from moonface.signal.engine.v3.config_v3 import EngineConfigV3


def q_floor_for(name: str, cfg: EngineConfigV3) -> float:
    floors = {
        "BREAKOUT": cfg.q_floor_breakout,
        "PULLBACK": cfg.q_floor_pullback,
        "REVERSION": cfg.q_floor_reversion,
    }
    return floors[name]


def size_from_quality(name: str, quality: float, cfg: EngineConfigV3) -> float:
    """f(q) = clip((q - q_floor)/(1 - q_floor), 0, 1); fraction = base * f,
    capped at max_fraction. Below the floor -> 0.0 (the sole veto)."""
    floor = q_floor_for(name, cfg)
    if quality < floor or floor >= 1.0:
        return 0.0
    f = (quality - floor) / (1.0 - floor)
    f = 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)
    return min(cfg.base_fraction + f * (cfg.max_fraction - cfg.base_fraction),
               cfg.max_fraction)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_sizing.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/sizing.py tests/test_v3_sizing.py
git diff --cached --stat
git commit -m "feat(v3): size-only quality->fraction curve"
```

---

### Task 10: `decide_v3` orchestrator + the core-invariant tests

**Files:**
- Create: `src/moonface/signal/engine/v3/decide.py`
- Test: `tests/test_v3_decide.py`

**Interfaces:**
- Consumes: `build_context`, `MechanismSignal` (Task 4); `classify_regime`, `Regime`, `DirState`, `VolState` (Task 3); `select_mechanism`, `MECHANISMS` (Task 8); `size_from_quality` (Task 9); `EngineConfigV3` (Task 1).
- Produces: `DecisionV3` (frozen dataclass: `action: str`, `direction: int`, `mechanism: str | None`, `regime: Regime`, `quality: float | None`, `risk_fraction: float`, `detail: str`), `decide_v3(candles, index, cfg) -> DecisionV3`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_v3_decide.py
"""decide_v3 orchestration + the spec-2 core invariant (score never trades)."""
import moonface.signal.engine.v3.decide as decide_mod
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.decide import DecisionV3, decide_v3
from moonface.signal.engine.v3.mechanisms.base import MechanismSignal
from moonface.signal.engine.v3.regime import DirState, Regime, VolState

from tests.helpers_v3 import uptrend

CFG = EngineConfigV3()


class _Spy:
    def __init__(self, name, signal):
        self.name = name
        self.signal = signal
        self.calls = 0

    def evaluate(self, ctx, regime):
        self.calls += 1
        return self.signal


def _force_regime(monkeypatch, regime):
    monkeypatch.setattr(decide_mod, "classify_regime", lambda candles, cfg: regime)


def test_extreme_vol_waits_before_any_selection(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.EXTREME))
    called = {"select": False}
    monkeypatch.setattr(decide_mod, "select_mechanism",
                        lambda r: called.__setitem__("select", True))
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and called["select"] is False


def test_empty_cell_waits(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.RANGING, VolState.HIGH))
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and d.mechanism is None


def test_nontriggering_bar_never_enters_even_with_max_quality(monkeypatch):
    """Core invariant: quality cannot create a trade when direction == 0."""
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    spy = _Spy("BREAKOUT", MechanismSignal(0, 1.0, "no trigger"))
    monkeypatch.setattr(decide_mod, "MECHANISMS", {"BREAKOUT": spy})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT"


def test_exactly_one_mechanism_is_consulted(monkeypatch):
    """Core invariant: no second mechanism is ever consulted on a bar."""
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    chosen = _Spy("BREAKOUT", MechanismSignal(1, 0.9, "hit"))
    other = _Spy("REVERSION", MechanismSignal(-1, 0.9, "should not run"))
    monkeypatch.setattr(decide_mod, "MECHANISMS",
                        {"BREAKOUT": chosen, "REVERSION": other})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "ENTER" and d.direction == 1
    assert chosen.calls == 1 and other.calls == 0
    assert d.risk_fraction > 0.0


def test_degenerate_quality_veto_waits(monkeypatch):
    _force_regime(monkeypatch, Regime(DirState.TRENDING_UP, VolState.NORMAL))
    spy = _Spy("BREAKOUT", MechanismSignal(1, 0.05, "below floor"))
    monkeypatch.setattr(decide_mod, "MECHANISMS", {"BREAKOUT": spy})
    monkeypatch.setattr(decide_mod, "select_mechanism", lambda r: "BREAKOUT")
    d = decide_v3(uptrend(140), 139, CFG)
    assert d.action == "WAIT" and d.risk_fraction == 0.0


def test_decision_is_frozen_and_serializable_shape():
    d = decide_v3(uptrend(140), 139, CFG)
    assert isinstance(d, DecisionV3)
    assert d.action in ("ENTER", "WAIT")
    assert d.risk_fraction >= 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_v3_decide.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.engine.v3.decide'`

- [ ] **Step 3: Write the implementation**

```python
# src/moonface/signal/engine/v3/decide.py
"""v3 orchestrator: classify -> select one mechanism -> trigger -> size.

The daemon entrypoint. Exactly one mechanism is consulted per bar and nothing
on the path sums — the spec-2 core invariant is enforced structurally here and
asserted in tests/test_v3_decide.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.foundation.models import Candle
from moonface.signal.engine.v3.config_v3 import EngineConfigV3
from moonface.signal.engine.v3.matrix import MECHANISMS, select_mechanism
from moonface.signal.engine.v3.mechanisms.base import build_context
from moonface.signal.engine.v3.regime import Regime, VolState, classify_regime
from moonface.signal.engine.v3.sizing import size_from_quality


@dataclass(frozen=True)
class DecisionV3:
    action: str            # "ENTER" | "WAIT"
    direction: int         # -1, 0, +1
    mechanism: str | None
    regime: Regime
    quality: float | None
    risk_fraction: float   # 0.0 on WAIT
    detail: str


def _wait(regime: Regime, mechanism: str | None, detail: str) -> DecisionV3:
    return DecisionV3("WAIT", 0, mechanism, regime, None, 0.0, detail)


def decide_v3(candles: list[Candle], index: int,
              cfg: EngineConfigV3) -> DecisionV3:
    regime = classify_regime(candles[: index + 1], cfg)

    if regime.vol_state == VolState.EXTREME:
        return _wait(regime, None, "extreme volatility — standing flat")

    name = select_mechanism(regime)
    if name is None:
        return _wait(regime, None, f"empty cell {regime.dir_state.value}"
                     f"/{regime.vol_state.value} — standing flat")

    ctx = build_context(candles, index, cfg)
    signal = MECHANISMS[name].evaluate(ctx, regime)
    if signal.direction == 0:
        return _wait(regime, name, f"{name} no trigger: {signal.detail}")

    fraction = size_from_quality(name, signal.quality, cfg)
    if fraction == 0.0:
        return _wait(regime, name,
                     f"{name} quality {signal.quality:.3f} below floor")

    return DecisionV3(
        action="ENTER", direction=signal.direction, mechanism=name,
        regime=regime, quality=signal.quality, risk_fraction=fraction,
        detail=f"ENTER {name} dir={signal.direction} "
               f"q={signal.quality:.3f} frac={fraction:.4f} "
               f"[{regime.dir_state.value}/{regime.vol_state.value}]",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_v3_decide.py -q`
Expected: 7 passed. If `test_decision_is_frozen_and_serializable_shape` produces WAIT (the random `uptrend` bar may not trigger BREAKOUT), that is fine — the assertion only checks the shape, not the action.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/engine/v3/decide.py tests/test_v3_decide.py
git diff --cached --stat
git commit -m "feat(v3): decide_v3 orchestrator + core-invariant tests"
```

---

### Task 11: Full-suite green + frozen forward registration

**Files:**
- Create: `experiments/engine/ENGINE_V3_FORWARD_REGISTRATION.md`
- Test: (whole suite — no new test file)

**Interfaces:**
- Consumes: `engine_hash_v3`, `EngineConfigV3` (Task 1).
- Produces: the frozen pre-registration doc with the pinned hash. No source changes.

- [ ] **Step 1: Confirm the entire suite is green (v2.2 untouched)**

Run: `.venv/bin/pytest -q`
Expected: all pass, including the pre-existing v2.2 tests (`test_engine_config.py`, `test_engine_calibration_pass.py`, `test_engine_confluence.py`).

- [ ] **Step 2: Print the pinned v3 hash to transcribe into the registration**

Run: `.venv/bin/python -c "from moonface.signal.engine.v3.config_v3 import EngineConfigV3, engine_hash_v3; print(engine_hash_v3(EngineConfigV3()))"`
Expected: a 64-char hex string. Copy it into the doc below in place of `<PASTE_HASH>`.

- [ ] **Step 3: Write the frozen forward registration**

```markdown
# Engine v3 — Regime-Mechanism — Forward Registration (FROZEN)

**Engine:** v3 (regime-mechanism matrix). Spec:
`docs/research-log/specs/2026-07-06-regime-mechanism-engine-v3-design.md`.
**Pinned hash (`engine_hash_v3(EngineConfigV3())`):** `<PASTE_HASH>`
**Registered:** 2026-07-06. **Status:** paper, disabled by default.

## Architecture under test

Regime (`trend/range × volatility`) selects exactly one specialist mechanism
(`BREAKOUT` / `PULLBACK` / `REVERSION`); the mechanism trigger is the sole
trade decision; a size-only quality score scales the position and vetoes
degenerate cases. No trade is created by summing confirmations. `RANGING×HIGH`
and `EXTREME` vol stand flat by design.

## The falsifiable bet (spec §11)

Prior regime work (regime-selector, regime-overlay) failed because regime
*filtered an additive score*. Here regime is a *selector that restricts trading
to where one specialist has edge*, and empty cells are first-class. Bet:
selection-not-summation with size-only scoring survives a forward window where
confluence did not.

## Frozen evaluation protocol

- **Horizon / sample:** verdict at the earlier of 6 months of paper or ≥ 30
  closed setups.
- **Baseline:** frozen v2.2 (hash `b4924f8e…`) over the same forward window.
- **Promotion bar (all required):** net-R > 0 after 3× cost stress; max
  drawdown-R no worse than v2.2; ≥ 1 mechanism contributes > 0 net-R on its own
  cells. Failing any → CLOSED NEGATIVE on the *selection* architecture.
- **Discipline:** no constant changes after this freeze. Any change = new
  ENGINE_VERSION + new hash + new registration. Starting the paper clock and
  swapping the daemon from v2.2 is a human step, out of scope for this build.
```

- [ ] **Step 4: Commit**

```bash
git add experiments/engine/ENGINE_V3_FORWARD_REGISTRATION.md
git diff --cached --stat
git commit -m "docs(v3): frozen forward registration with pinned hash"
```

---

## Notes for the implementer

- Work tasks in order; each mechanism (Tasks 5–7) depends only on Task 4's base, so they are otherwise independent.
- The synthetic candle helpers in `tests/helpers_v3.py` are the only fixtures; do not pull in the v2.2 `tests/helpers_audit.py` walk series (it is near-random and won't produce clean regimes).
- If any regime/vol synthetic lands one bucket off, adjust the *helper call arguments* (step/wick/length) in the test — never the frozen config cutpoints. The cutpoints are part of the engine's registered identity.
- `decide_v3(candles, index, cfg)` is the daemon seam. Wiring it into the live loop and starting the paper clock is deliberately out of scope (a human step per the registration).
