# Baseline Composite Signal Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-on "baseline" tier to `moonface-signal` that emits an actionable BTC perp `LONG`/`SHORT`/`WAIT` call with `confidence`, `reason`, `timeframe`, and `risk_notes` — honestly labelled as a heuristic with no validated edge — sitting below the existing live/paper/participation tiers and never executing trades.

**Architecture:** A new `signal/baseline.py` holds pure state-voter functions (trend-channel, close-vs-MA, funding z-score), a volatility-rank damp, an aggregation rule (confidence = weighted agreement), a fail-safe `BaselineConfig` loader (on by default), and `evaluate_baseline()` which assembles a `Signal`. The shared `Signal` dataclass gains four defaulted fields. `signal/cli.py` wires baseline as the lowest rung of the resolution ladder in both `run()` and `watch()`, reusing the existing journal and `--alert-cmd` surface.

**Tech Stack:** Python 3.11+, stdlib `unittest`/`pytest`, the existing `moonface.signal` and `moonface.backtest.edge` packages.

**Spec:** `docs/research-log/specs/2026-06-15-baseline-signal-tier-design.md`

**Design refinement vs. spec §3.2/§4.1:** The spec said voters "reuse `generate_entries`". Two of the chosen generators (`price_vs_ma`, `funding_fade`) are edge-triggered (fire only on the cross/flip bar), which would make a per-candle bot emit WAIT almost always. The voters are therefore implemented as **current-state reads** of the same indicators. `donchian_break` is genuinely state-based and is reused directly. The voter contract (return `+1`/`-1`/`0`; confidence = weighted agreement) is unchanged.

---

## File Structure

- **Modify** `src/moonface/signal/evaluate.py` — extend the `Signal` dataclass with `confidence`, `timeframe`, `risk_notes`, `tier` (all defaulted; existing call-sites unaffected).
- **Create** `src/moonface/signal/baseline.py` — voters, vol-rank damp, aggregation, `BaselineConfig` + `load_baseline_config` + `baseline_hash`, and `evaluate_baseline`.
- **Modify** `src/moonface/signal/cli.py` — `--baseline` arg, `_emit_baseline`, and baseline as ladder step 4 in `run()` and `watch()`.
- **Create** `tests/test_signal_baseline.py` — voters, vol-rank, aggregation, config loader, `evaluate_baseline`.
- **Modify** `tests/test_signal_cli.py` — baseline-on emission, structural-WAIT when disabled, precedence, JSON fields.

---

## Task 1: Extend the `Signal` dataclass

**Files:**
- Modify: `src/moonface/signal/evaluate.py:11-18`
- Test: `tests/test_signal_evaluate.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_signal_evaluate.py`:

```python
def test_signal_has_defaulted_baseline_fields():
    from moonface.signal.evaluate import Signal
    # backward-compatible 5-positional construction still works
    s = Signal("WAIT", None, None, None, "because")
    assert s.confidence == 0.0
    assert s.timeframe == ""
    assert s.risk_notes == ""
    assert s.tier == ""
    # new fields are settable by keyword
    s2 = Signal("LONG", 100.0, 95.0, 0.01, "fired",
                confidence=0.6, timeframe="4h", risk_notes="r", tier="baseline")
    assert s2.confidence == 0.6
    assert s2.tier == "baseline"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_evaluate.py::test_signal_has_defaulted_baseline_fields -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'confidence'`.

- [ ] **Step 3: Add the fields**

In `src/moonface/signal/evaluate.py`, extend the dataclass (keep existing fields and order; append the four new ones after `kill_switch`):

```python
@dataclass(frozen=True)
class Signal:
    decision: str               # "LONG" | "SHORT" | "WAIT"
    price: float | None
    invalidation: float | None
    fraction: float | None
    reason: str
    kill_switch: bool = False   # participation advisor: realized-drawdown halt
    confidence: float = 0.0     # agreement strength [0,1]; NOT P(profit)
    timeframe: str = ""         # e.g. "4h"
    risk_notes: str = ""        # invalidation / sizing / caveat, human-readable
    tier: str = ""              # "" | "live" | "paper" | "participation" | "baseline"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_evaluate.py -v`
Expected: PASS (new test + all existing tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/evaluate.py tests/test_signal_evaluate.py
git diff --cached --stat
git commit -m "feat(signal): extend Signal with confidence/timeframe/risk_notes/tier"
```

---

## Task 2: Baseline voters, vol-rank damp, and aggregation

**Files:**
- Create: `src/moonface/signal/baseline.py`
- Test: `tests/test_signal_baseline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_signal_baseline.py`:

```python
import math

from moonface.models import Candle

_H4_MS = 4 * 3_600_000


def _candles(closes, highs=None, lows=None):
    """Build candles from close prices; highs/lows default to close."""
    out = []
    ts = 1_600_000_000_000
    for k, close in enumerate(closes):
        hi = close if highs is None else highs[k]
        lo = close if lows is None else lows[k]
        out.append(Candle(ts, close, hi, lo, close, 1000.0))
        ts += _H4_MS
    return out


class TestVoters:
    def test_trend_breakout_long_when_close_above_prior_high(self):
        from moonface.signal.baseline import trend_breakout_vote
        # n=3; last close breaks above the max of the prior 3 highs
        candles = _candles([10, 11, 12, 13, 20])
        assert trend_breakout_vote(candles, n=3) == 1

    def test_trend_breakout_short_when_close_below_prior_low(self):
        from moonface.signal.baseline import trend_breakout_vote
        candles = _candles([20, 19, 18, 17, 5])
        assert trend_breakout_vote(candles, n=3) == -1

    def test_trend_breakout_neutral_inside_channel(self):
        from moonface.signal.baseline import trend_breakout_vote
        candles = _candles([10, 20, 5, 30, 15])
        assert trend_breakout_vote(candles, n=3) == 0

    def test_trend_confirm_sign_of_close_minus_sma(self):
        from moonface.signal.baseline import trend_confirm_vote
        rising = _candles([1, 2, 3, 4, 100])
        assert trend_confirm_vote(rising, period=4) == 1
        falling = _candles([100, 99, 98, 97, 1])
        assert trend_confirm_vote(falling, period=4) == -1

    def test_funding_fade_short_on_crowded_long(self):
        from moonface.signal.baseline import funding_fade_vote
        funding = [0.0] * 9 + [0.10]      # last value is a large positive spike
        assert funding_fade_vote(funding, window=10, z_thr=1.5) == -1

    def test_funding_fade_long_on_crowded_short(self):
        from moonface.signal.baseline import funding_fade_vote
        funding = [0.0] * 9 + [-0.10]
        assert funding_fade_vote(funding, window=10, z_thr=1.5) == 1

    def test_funding_fade_abstains_without_data(self):
        from moonface.signal.baseline import funding_fade_vote
        assert funding_fade_vote(None, window=10, z_thr=1.5) == 0
        assert funding_fade_vote([0.0] * 3, window=10, z_thr=1.5) == 0


class TestVolRatio:
    def test_none_without_enough_history(self):
        from moonface.signal.baseline import vol_ratio
        assert vol_ratio(_candles([1, 2, 3]), window=5) is None

    def test_calm_then_spike_ratio_above_one(self):
        from moonface.signal.baseline import vol_ratio
        closes = [100.0]
        for _ in range(60):
            closes.append(closes[-1] * 1.001)      # long calm baseline
        for _ in range(6):
            closes.append(closes[-1] * 1.05)       # recent vol spike
        r = vol_ratio(_candles(closes), window=10)
        assert r is not None and r > 1.5

    def test_steady_regime_ratio_near_one(self):
        from moonface.signal.baseline import vol_ratio
        closes = [100.0 * (1.002 ** k) for k in range(80)]
        r = vol_ratio(_candles(closes), window=10)
        assert r is not None and 0.8 < r < 1.2


class TestAggregate:
    def test_unanimous_long_full_agreement(self):
        from moonface.signal.baseline import aggregate
        decision, agreement = aggregate(
            {"a": 1, "b": 1, "c": 1}, {"a": 1.0, "b": 1.0, "c": 1.0}, 0.5)
        assert decision == "LONG"
        assert agreement == 1.0

    def test_split_below_floor_is_wait(self):
        from moonface.signal.baseline import aggregate
        decision, agreement = aggregate(
            {"a": 1, "b": -1, "c": 0}, {"a": 1.0, "b": 1.0, "c": 1.0}, 0.5)
        assert decision == "WAIT"
        assert math.isclose(agreement, 0.0)

    def test_majority_short_above_floor(self):
        from moonface.signal.baseline import aggregate
        decision, agreement = aggregate(
            {"a": -1, "b": -1, "c": 1}, {"a": 1.0, "b": 1.0, "c": 1.0}, 0.5)
        assert decision == "SHORT"
        assert math.isclose(agreement, 1.0 / 3.0)  # net=-1, total=3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_baseline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.signal.baseline'`.

- [ ] **Step 3: Create the module with the pure functions**

Create `src/moonface/signal/baseline.py`:

```python
"""Baseline composite signal tier (spec 2026-06-15).

The falsification program (docs/findings/PROGRAM_CONCLUSION.md) found no OOS-valid
edge on free BTC data, so this tier makes NO expectancy claim. It emits an
honest, clearly-labelled HEURISTIC LONG/SHORT/WAIT by polling a few indicator
STATES and reporting how strongly they agree (`confidence`). It executes nothing
and sits below the live/paper/participation tiers in the CLI resolution ladder.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from statistics import fmean, pstdev

from moonface.models import Candle


def trend_breakout_vote(candles: list[Candle], n: int) -> int:
    """Donchian-channel STATE at the last bar (donchian_break logic, read as a
    state): close above the prior-n high -> +1, below the prior-n low -> -1,
    inside -> 0."""
    i = len(candles) - 1
    if i < n:
        return 0
    prior_high = max(c.high for c in candles[i - n:i])
    prior_low = min(c.low for c in candles[i - n:i])
    if candles[i].close > prior_high:
        return 1
    if candles[i].close < prior_low:
        return -1
    return 0


def trend_confirm_vote(candles: list[Candle], period: int) -> int:
    """Close vs SMA STATE: above -> +1, below -> -1, equal/short-history -> 0."""
    i = len(candles) - 1
    if i + 1 < period:
        return 0
    closes = [c.close for c in candles]
    ma = fmean(closes[i - period + 1:i + 1])
    if closes[i] == ma:
        return 0
    return 1 if closes[i] > ma else -1


def funding_fade_vote(funding: list[float | None] | None, window: int,
                      z_thr: float) -> int:
    """Rolling-z STATE of funding (funding_fade logic, read as a state): crowded
    long (z >= +z_thr) -> fade SHORT (-1), crowded short (z <= -z_thr) -> LONG
    (+1). Abstains (0) when funding data is missing or insufficient."""
    if funding is None or len(funding) < window:
        return 0
    recent = funding[-window:]
    if any(v is None for v in recent):
        return 0
    mean = fmean(recent)
    sd = pstdev(recent)
    if sd <= 0:
        return 0
    z = (recent[-1] - mean) / sd
    if z >= z_thr:
        return -1
    if z <= -z_thr:
        return 1
    return 0


def vol_ratio(candles: list[Candle], window: int) -> float | None:
    """Ratio of short-term realized vol (mean abs log-return over the last
    `window` bars) to the full-window baseline vol. ~1 in a steady regime, >1
    when volatility is spiking. None without >= 2*window bars."""
    if len(candles) < window * 2:
        return None
    closes = [c.close for c in candles]
    rets = [abs(math.log(closes[k] / closes[k - 1]))
            for k in range(1, len(closes))]
    long_vol = fmean(rets)
    short_vol = fmean(rets[-window:])
    if long_vol <= 0:
        return 1.0
    return short_vol / long_vol


def aggregate(votes: dict[str, int], weights: dict[str, float],
              agreement_floor: float) -> tuple[str, float]:
    """Weighted-vote decision. Returns (decision, agreement) where
    agreement = |net|/total in [0,1]. Below the floor (or a zero net) -> WAIT."""
    total = sum(weights[k] for k in votes)
    if total <= 0:
        return "WAIT", 0.0
    net = sum(weights[k] * votes[k] for k in votes)
    agreement = abs(net) / total
    if net == 0 or agreement < agreement_floor:
        return "WAIT", agreement
    return ("LONG" if net > 0 else "SHORT"), agreement
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_baseline.py -v`
Expected: PASS (all `TestVoters`, `TestVolRank`, `TestAggregate` cases).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/baseline.py tests/test_signal_baseline.py
git diff --cached --stat
git commit -m "feat(signal): baseline voters, vol-rank damp, weighted aggregation"
```

---

## Task 3: `BaselineConfig` loader and hash

**Files:**
- Modify: `src/moonface/signal/baseline.py`
- Test: `tests/test_signal_baseline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_signal_baseline.py`:

```python
class TestBaselineConfig:
    def test_missing_file_returns_enabled_default(self, tmp_path):
        from moonface.signal.baseline import load_baseline_config
        cfg = load_baseline_config(tmp_path / "absent.json")
        assert cfg.enabled is True
        assert cfg.asset["symbol"] == "BTC/USDT:USDT"
        assert cfg.asset["timeframe"] == "4h"
        assert cfg.agreement_floor == 0.5

    def test_invalid_json_falls_back_to_default(self, tmp_path):
        from moonface.signal.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text("{not json")
        cfg = load_baseline_config(p)
        assert cfg.enabled is True

    def test_explicit_disable_is_honored(self, tmp_path):
        import json
        from moonface.signal.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"enabled": False}))
        cfg = load_baseline_config(p)
        assert cfg.enabled is False

    def test_overrides_merge_onto_defaults(self, tmp_path):
        import json
        from moonface.signal.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"donchian_n": 55, "agreement_floor": 0.9}))
        cfg = load_baseline_config(p)
        assert cfg.donchian_n == 55
        assert cfg.agreement_floor == 0.9
        assert cfg.ma_period == 50  # untouched default

    def test_hash_excludes_enabled_flag(self, tmp_path):
        import json
        from moonface.signal.baseline import (baseline_hash,
                                              load_baseline_config)
        a = load_baseline_config(tmp_path / "absent.json")
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"enabled": False}))
        b = load_baseline_config(p)
        # flipping only `enabled` must not change the journal identity
        assert baseline_hash(a) == baseline_hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_baseline.py::TestBaselineConfig -v`
Expected: FAIL — `ImportError: cannot import name 'load_baseline_config'`.

- [ ] **Step 3: Add the config dataclass, loader, and hash**

Append to `src/moonface/signal/baseline.py`:

```python
def _default_asset() -> dict:
    return {"exchange": "binance", "symbol": "BTC/USDT:USDT",
            "timeframe": "4h", "funding_symbol": "BTC/USDT:USDT"}


def _default_weights() -> dict:
    return {"trend_breakout": 1.0, "trend_confirm": 1.0, "funding_fade": 1.0}


@dataclass(frozen=True)
class BaselineConfig:
    """Tunable composite parameters. Absent/invalid file -> these defaults, so
    the baseline tier is ON unless the human writes `{"enabled": false}`."""

    enabled: bool = True
    asset: dict = field(default_factory=_default_asset)
    donchian_n: int = 20
    ma_period: int = 50
    funding_window: int = 60
    funding_z: float = 1.5
    vol_window: int = 30
    high_vol_ratio: float = 1.5         # damp confidence above this vol ratio
    extreme_vol_damp: float = 0.5       # multiplier applied in the loud regime
    wait_vol_ratio: float = 2.5         # force WAIT above this vol ratio
    weights: dict = field(default_factory=_default_weights)
    agreement_floor: float = 0.5
    atr_period: int = 14
    k_stop: float = 2.0
    risk_fraction: float = 0.0005       # suggested size; honest, tiny default


_CONFIG_FIELDS = {
    "enabled", "asset", "donchian_n", "ma_period", "funding_window",
    "funding_z", "vol_window", "high_vol_ratio", "extreme_vol_damp",
    "wait_vol_ratio", "weights", "agreement_floor", "atr_period", "k_stop",
    "risk_fraction",
}


def load_baseline_config(path) -> BaselineConfig:
    """Fail-safe, on-by-default loader: a missing or invalid file yields the
    default (enabled) composite; a valid file's recognised keys override the
    defaults. Never returns None — the baseline tier always resolves."""
    from pathlib import Path
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            return BaselineConfig()
        overrides = {k: v for k, v in raw.items() if k in _CONFIG_FIELDS}
        return BaselineConfig(**overrides)
    except (OSError, ValueError, TypeError):
        return BaselineConfig()


def baseline_hash(cfg: BaselineConfig) -> str:
    """Journal identity of the signal-relevant content. `enabled` is excluded so
    silencing/unsilencing the tier does not start a new forward-record segment."""
    payload = {
        "asset": cfg.asset, "donchian_n": cfg.donchian_n,
        "ma_period": cfg.ma_period, "funding_window": cfg.funding_window,
        "funding_z": cfg.funding_z, "vol_window": cfg.vol_window,
        "high_vol_ratio": cfg.high_vol_ratio,
        "extreme_vol_damp": cfg.extreme_vol_damp,
        "wait_vol_ratio": cfg.wait_vol_ratio, "weights": cfg.weights,
        "agreement_floor": cfg.agreement_floor, "atr_period": cfg.atr_period,
        "k_stop": cfg.k_stop, "risk_fraction": cfg.risk_fraction,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_baseline.py::TestBaselineConfig -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/baseline.py tests/test_signal_baseline.py
git diff --cached --stat
git commit -m "feat(signal): BaselineConfig fail-safe loader (on by default) + hash"
```

---

## Task 4: `evaluate_baseline` — assemble the Signal

**Files:**
- Modify: `src/moonface/signal/baseline.py`
- Test: `tests/test_signal_baseline.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_signal_baseline.py`:

```python
class TestEvaluateBaseline:
    def _bundle(self, closes, funding=None):
        from moonface.research.bundle import DataBundle
        return DataBundle(candles=_candles(closes), funding=funding)

    def test_returns_wait_signal_with_baseline_tier_on_short_history(self):
        from moonface.signal.baseline import BaselineConfig, evaluate_baseline
        sig = evaluate_baseline(BaselineConfig(), self._bundle([1, 2, 3]), 0)
        assert sig.decision == "WAIT"
        assert sig.tier == "baseline"
        assert sig.timeframe == "4h"

    def test_strong_uptrend_emits_long_with_label_and_risk_notes(self):
        from moonface.research.synth import make_candles
        from moonface.research.bundle import DataBundle
        from moonface.signal.baseline import BaselineConfig, evaluate_baseline
        # steady drift up -> breakout + above-MA agree; funding abstains (None)
        candles = make_candles(n=200, drift=0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.decision == "LONG"
        assert sig.tier == "baseline"
        assert 0.0 < sig.confidence <= 1.0
        assert sig.price == candles[-1].close
        assert sig.invalidation is not None and sig.invalidation < sig.price
        assert "no expectancy claim" in sig.risk_notes.lower()
        assert "not a validated edge" in sig.reason.lower()
        assert sig.fraction == BaselineConfig().risk_fraction

    def test_short_invalidation_sits_above_price(self):
        from moonface.research.synth import make_candles
        from moonface.research.bundle import DataBundle
        from moonface.signal.baseline import BaselineConfig, evaluate_baseline
        candles = make_candles(n=200, drift=-0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.decision == "SHORT"
        assert sig.invalidation > sig.price

    def test_confidence_never_exceeds_one(self):
        from moonface.research.synth import make_candles
        from moonface.research.bundle import DataBundle
        from moonface.signal.baseline import BaselineConfig, evaluate_baseline
        candles = make_candles(n=200, drift=0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.confidence <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signal_baseline.py::TestEvaluateBaseline -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_baseline'`.

- [ ] **Step 3: Implement `evaluate_baseline`**

Append to `src/moonface/signal/baseline.py` (add the imports shown at the top of the snippet to the module's existing import block):

```python
from moonface.signal.evaluate import Signal


_NO_CLAIM = "heuristic — NOT a validated edge, no expectancy claim"


def _regime_factor(ratio: float | None, cfg: BaselineConfig) -> tuple[float, bool]:
    """Returns (confidence multiplier, force_wait). High vol damps confidence;
    extreme vol forces WAIT."""
    if ratio is None:
        return 1.0, False
    if ratio >= cfg.wait_vol_ratio:
        return 0.0, True
    if ratio >= cfg.high_vol_ratio:
        return cfg.extreme_vol_damp, False
    return 1.0, False


def _wait(reason: str, confidence: float, tf: str) -> Signal:
    return Signal("WAIT", None, None, None, reason, confidence=round(confidence, 4),
                  timeframe=tf, risk_notes=_NO_CLAIM, tier="baseline")


def evaluate_baseline(cfg: BaselineConfig, bundle, now_ms: int) -> Signal:
    """Composite heuristic signal for the last closed candle. Reads OHLCV (+
    funding when present); never executes anything; always tier='baseline'."""
    from moonface.backtest.edge.evaluate import _risk
    from moonface.signal.evaluate import _sentinel_extended

    candles = bundle.candles
    tf = cfg.asset["timeframe"]
    required = max(cfg.vol_window * 2, cfg.donchian_n + 1, cfg.ma_period,
                   cfg.atr_period + 2)
    if len(candles) < required:
        return _wait("insufficient history for the baseline window", 0.0, tf)

    votes = {
        "trend_breakout": trend_breakout_vote(candles, cfg.donchian_n),
        "trend_confirm": trend_confirm_vote(candles, cfg.ma_period),
        "funding_fade": funding_fade_vote(bundle.funding, cfg.funding_window,
                                          cfg.funding_z),
    }
    decision, agreement = aggregate(votes, cfg.weights, cfg.agreement_floor)
    damp, force_wait = _regime_factor(vol_ratio(candles, cfg.vol_window), cfg)
    confidence = agreement * damp

    agree_str = (f"votes trend_breakout={votes['trend_breakout']:+d}"
                 f" trend_confirm={votes['trend_confirm']:+d}"
                 f" funding_fade={votes['funding_fade']:+d}")
    if force_wait:
        return _wait(f"extreme volatility regime — standing flat; {agree_str}",
                     confidence, tf)
    if decision == "WAIT":
        return _wait(f"no directional agreement; {agree_str}", confidence, tf)

    last_index = len(candles) - 1
    unit = _risk(_sentinel_extended(bundle).candles, last_index, cfg.k_stop,
                 cfg.atr_period)
    if unit is None:
        return _wait("ATR risk unit undefined on this window", confidence, tf)
    price = candles[last_index].close
    invalidation = price - unit if decision == "LONG" else price + unit
    atr = unit / cfg.k_stop
    risk_notes = (f"invalidation {invalidation:.2f} (1R=ATR{cfg.atr_period}"
                  f"~{atr:.0f}), suggested f={cfg.risk_fraction}; {_NO_CLAIM}")
    reason = (f"{decision} on {agree_str} (agreement {agreement:.2f}) —"
              f" {_NO_CLAIM}")
    return Signal(decision, price, round(invalidation, 2), cfg.risk_fraction,
                  reason, confidence=round(confidence, 4), timeframe=tf,
                  risk_notes=risk_notes, tier="baseline")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_signal_baseline.py -v`
Expected: PASS (every class in the file).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/signal/baseline.py tests/test_signal_baseline.py
git diff --cached --stat
git commit -m "feat(signal): evaluate_baseline assembles the labelled composite Signal"
```

---

## Task 5: Wire baseline into the CLI as the lowest tier

**Files:**
- Modify: `src/moonface/signal/cli.py`
- Test: `tests/test_signal_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_signal_cli.py` (the file already imports `json`, `pytest`, `DataBundle`, `make_candles`, `cli`, `read_entries`, and defines `_H4_MS`, `VALID`, `_fresh_candles`):

```python
def test_baseline_emitted_when_no_strategy_or_policy(tmp_path, capsys,
                                                     monkeypatch):
    now_ms = 1_700_000_000_000 - (1_700_000_000_000 % _H4_MS)
    candles = make_candles(400, start_ts=now_ms - 400 * _H4_MS,
                           drift=0.01, noise=0.001)
    monkeypatch.setattr(cli, "_now_ms", lambda: now_ms)
    monkeypatch.setattr(cli, "load_bundle",
                        lambda asset, s, e, c: DataBundle(candles=candles))
    rc = cli.run(["--strategy", str(tmp_path / "absent.json"),
                  "--policy", str(tmp_path / "absent-policy.json"),
                  "--baseline", str(tmp_path / "absent-baseline.json"),
                  "--journal", str(tmp_path / "j.jsonl"), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "baseline"
    assert payload["actionable"] in ("LONG", "SHORT", "WAIT")
    assert payload["tier"] == "baseline"
    assert "confidence" in payload and "timeframe" in payload
    assert "risk_notes" in payload
    # the emission is journaled under the baseline version
    assert len(read_entries(tmp_path / "j.jsonl")) == 1


def test_baseline_disabled_prints_structural_wait(tmp_path, capsys, monkeypatch):
    (tmp_path / "baseline.json").write_text(json.dumps({"enabled": False}))
    rc = cli.run(["--strategy", str(tmp_path / "absent.json"),
                  "--policy", str(tmp_path / "absent-policy.json"),
                  "--baseline", str(tmp_path / "baseline.json"),
                  "--journal", str(tmp_path / "j.jsonl")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WAIT (no validated strategy)" in out
    assert read_entries(tmp_path / "j.jsonl") == []


def test_paper_strategy_supersedes_baseline(tmp_path, capsys, monkeypatch):
    strategy_path = tmp_path / "strategy.json"
    strategy_path.write_text(json.dumps(VALID))
    now_ms = 1_700_000_000_000 - (1_700_000_000_000 % _H4_MS)
    candles = _fresh_candles(now_ms)
    monkeypatch.setattr(cli, "_now_ms", lambda: now_ms)
    monkeypatch.setattr(cli, "load_bundle",
                        lambda asset, s, e, c: DataBundle(candles=candles))
    rc = cli.run(["--strategy", str(strategy_path),
                  "--baseline", str(tmp_path / "absent-baseline.json"),
                  "--journal", str(tmp_path / "j.jsonl"), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "paper"   # baseline did NOT take over
```

Also update the existing `test_no_strategy_prints_wait`: it now needs the baseline disabled to still assert the structural WAIT. Replace its body with:

```python
def test_no_strategy_prints_wait(tmp_path, capsys, monkeypatch):
    (tmp_path / "baseline.json").write_text(json.dumps({"enabled": False}))
    rc = cli.run(["--strategy", str(tmp_path / "absent.json"),
                  "--policy", str(tmp_path / "absent-policy.json"),
                  "--baseline", str(tmp_path / "baseline.json"),
                  "--journal", str(tmp_path / "j.jsonl")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WAIT (no validated strategy)" in out
    assert read_entries(tmp_path / "j.jsonl") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_signal_cli.py -k baseline -v`
Expected: FAIL — `--baseline` is an unknown argument (argparse `SystemExit`), and there is no baseline branch yet.

- [ ] **Step 3: Add the `--baseline` arg**

In `src/moonface/signal/cli.py`, inside `build_parser()`, after the `--policy` argument:

```python
    p.add_argument("--baseline", default="promotion/baseline.json",
                   help="baseline composite config; absent/invalid means the"
                        " on-by-default heuristic tier (no expectancy claim)")
```

- [ ] **Step 4: Add the `_emit_baseline` handler**

In `src/moonface/signal/cli.py`, add the import near the other signal imports:

```python
from moonface.signal.baseline import (baseline_hash, evaluate_baseline,
                                       load_baseline_config)
```

Add this function next to `_emit_participation`:

```python
def _emit_baseline(args: argparse.Namespace, cfg, bundle: DataBundle,
                   now: int, tf_ms: int):
    """Evaluate the baseline composite on the last closed candle, journal it,
    print it. Baseline signals are actionable as emitted but carry the explicit
    heuristic / no-expectancy-claim label — never a validated gate pass."""
    sig = evaluate_baseline(cfg, bundle, now)
    last = bundle.candles[-1]
    append_entry(args.journal, {
        "ts_ms": now,
        "candle_ts_ms": last.timestamp_ms,
        "decision": sig.decision,
        "price": sig.price,
        "invalidation": sig.invalidation,
        "fraction": sig.fraction,
        "status": "baseline",
        "strategy_version": baseline_hash(cfg),
        "confidence": sig.confidence,
        "reason": sig.reason,
    })
    payload = {
        "actionable": sig.decision,
        "status": "baseline",
        "tier": sig.tier,
        "price": sig.price,
        "invalidation": sig.invalidation,
        "fraction": sig.fraction,
        "confidence": sig.confidence,
        "timeframe": sig.timeframe,
        "risk_notes": sig.risk_notes,
        "reason": sig.reason,
        "candle_close_utc": last.timestamp_ms + tf_ms,
    }
    if args.as_json:
        print(json.dumps(payload))
    elif sig.decision == "WAIT":
        print(f"WAIT — {sig.reason} [BASELINE conf {sig.confidence}]")
    else:
        print(f"{sig.decision} @ {sig.price}, invalidation {sig.invalidation},"
              f" f={sig.fraction} — {sig.reason}"
              f" [BASELINE conf {sig.confidence}; {sig.timeframe}]"
              f" ({sig.risk_notes})")
    return sig
```

- [ ] **Step 5: Wire baseline into `run()`**

In `run()`, replace the `strategy is None` block (the part that currently handles `policy is None` / `not policy.enabled` by printing WAIT) so that those cases fall through to the baseline. The new control flow for the no-strategy path:

```python
    strategy = load_strategy(args.strategy)
    if strategy is None:
        policy = load_policy(args.policy)
        if policy is not None and policy.enabled:
            try:
                bundle, _end_ms, tf_ms = _fresh_bundle(args, policy.asset,
                                                       _now_ms())
            except DataError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                raise SystemExit(2)
            if args.report:
                from moonface.signal.participation import realized_drawdown_r
                print(json.dumps({
                    "status": "participation",
                    "realized_drawdown_r": round(realized_drawdown_r(
                        policy, read_entries(args.journal), bundle.candles), 4),
                    "note": "forward gate applies to promoted strategies only",
                }, indent=2, sort_keys=True))
                return 0
            _emit_participation(args, policy, bundle, _now_ms(), tf_ms)
            return 0
        # lowest tier: the on-by-default baseline composite
        cfg = load_baseline_config(args.baseline)
        if not cfg.enabled:
            payload = {"actionable": "WAIT", "status": "none",
                       "reason": "no validated strategy"}
            print(json.dumps(payload) if args.as_json
                  else "WAIT (no validated strategy)")
            return 0
        try:
            bundle, _end_ms, tf_ms = _fresh_bundle(args, cfg.asset, _now_ms())
        except DataError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        _emit_baseline(args, cfg, bundle, _now_ms(), tf_ms)
        return 0
```

(The promoted-strategy path below this block — `_fresh_bundle(... strategy.asset ...)`, `--report`, `_emit` — is unchanged.)

- [ ] **Step 6: Wire baseline into `watch()`**

In `watch()`, replace the tier-resolution head of the loop body so baseline is the fallback. Replace the block from `strategy = load_strategy(...)` through the `if strategy is None and policy is None:` / `elif ... not policy.enabled` branches with:

```python
        strategy = load_strategy(args.strategy)
        policy = None if strategy else load_policy(args.policy)
        use_policy = policy is not None and policy.enabled
        cfg = (load_baseline_config(args.baseline)
               if strategy is None and not use_policy else None)
        asset = (strategy.asset if strategy
                 else policy.asset if use_policy
                 else cfg.asset if cfg and cfg.enabled else None)
        tf_ms = TIMEFRAME_MS[asset["timeframe"] if asset
                             else DEFAULT_WATCH_TIMEFRAME]
        if asset is None:
            print("WAIT (no validated strategy)")
        else:
            try:
                bundle, _end_ms, tf_ms = _fresh_bundle(args, asset, _now_ms())
                last_ts = bundle.candles[-1].timestamp_ms
                version = (strategy_hash(strategy) if strategy
                           else policy_hash(policy) if use_policy
                           else baseline_hash(cfg))
                if not _already_journaled(args, version, last_ts):
                    if strategy is not None:
                        sig = _emit(args, strategy, bundle, _now_ms(), tf_ms)
                        if sig.decision != "WAIT":
                            _alert(args,
                                   f"{strategy.status} signal: {sig.decision} @"
                                   f" {sig.price}, invalidation {sig.invalidation},"
                                   f" f={sig.fraction}")
                        gate = forward_report(read_entries(args.journal),
                                              bundle.candles, strategy)["gate"]
                        if gate["passed"]:
                            _alert(args, "forward gate PASSED — paper->live"
                                         " review is unlocked (human decision)")
                    elif use_policy:
                        sig = _emit_participation(args, policy, bundle,
                                                  _now_ms(), tf_ms)
                        if sig.kill_switch:
                            _alert(args, f"participation kill switch:"
                                         f" {sig.reason}")
                        elif sig.decision != "WAIT":
                            _alert(args, f"participation signal:"
                                         f" {sig.decision} @ {sig.price},"
                                         f" f={sig.fraction}")
                    else:
                        sig = _emit_baseline(args, cfg, bundle, _now_ms(), tf_ms)
                        if sig.decision != "WAIT":
                            _alert(args, f"baseline signal: {sig.decision} @"
                                         f" {sig.price}, conf {sig.confidence},"
                                         f" f={sig.fraction}")
            except DataError as exc:
                _alert(args, str(exc))
```

(The trailing `now = _now_ms(); next_close = ...; sleep_fn(...)` tail of the loop is unchanged.)

- [ ] **Step 7: Run the CLI tests**

Run: `python -m pytest tests/test_signal_cli.py -v`
Expected: PASS (the three new baseline tests, the rewritten `test_no_strategy_prints_wait`, and every previously-passing CLI test).

- [ ] **Step 8: Commit**

```bash
git add src/moonface/signal/cli.py tests/test_signal_cli.py
git diff --cached --stat
git commit -m "feat(signal): wire on-by-default baseline tier into run() and watch()"
```

---

## Task 6: Full suite, lint, README, and live smoke

**Files:**
- Modify: `README.md`
- Verification only otherwise.

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: all green. If `tests/test_signal_participation.py` or any other test asserted the old "participation not mandated (policy disabled)" WAIT string from `run()`, update it to expect the baseline emission (a disabled policy now falls through to baseline) or set `enabled:false` in a baseline.json for that test, matching the pattern in `test_no_strategy_prints_wait`.

- [ ] **Step 2: Lint**

Run: `ruff check src/moonface/signal/ tests/test_signal_baseline.py tests/test_signal_cli.py`
Expected: no errors. Fix any import-order or line-length findings.

- [ ] **Step 3: Update the README Signal CLI section**

In `README.md`, under "## Signal CLI", add after the existing command list:

```markdown
With no promoted strategy and no participation mandate, the CLI now falls through
to an **on-by-default baseline tier**: a transparent composite of trend, MA, and
funding states that emits LONG/SHORT/WAIT with a `confidence` (agreement
strength, **not** a probability of profit), `timeframe`, and `risk_notes`. Every
baseline line is marked `[BASELINE — heuristic, NOT a validated edge]`. Write
`promotion/baseline.json` with `{"enabled": false}` to silence it and restore the
structural `WAIT (no validated strategy)` default. A promoted paper/live strategy
or an enabled participation mandate always supersedes the baseline.
```

- [ ] **Step 4: Live smoke (network; manual)**

Run:
```bash
moonface-signal --json
moonface-signal
```
Expected: a JSON object with `"status": "baseline"` and `confidence`/`timeframe`/`risk_notes`/`tier` keys, then a human line tagged `[BASELINE ...]`. (If the network/cache is unavailable this exits non-zero with a data error, which is correct — never a fake WAIT.)

- [ ] **Step 5: Commit**

```bash
git add README.md
git diff --cached --stat
git commit -m "docs(signal): document the on-by-default baseline tier"
```

---

## Self-Review Notes (addressed)

- **Spec §2 decision 1 (multi-signal composite)** → Task 2 voters + Task 4 aggregation/assembly.
- **Spec §2 decision 2 (baseline lowest tier, on by default)** → Task 3 `load_baseline_config` defaults enabled; Task 5 ladder wiring in `run()`/`watch()`; precedence regression-locked by `test_paper_strategy_supersedes_baseline`.
- **Spec §2 decision 3 (reuse delivery surface)** → Task 5 reuses `append_entry`/`--json`/`_alert`; no new network code; `--alert-cmd` carries the baseline message.
- **Spec §3.3 (OHLCV + funding only)** → funding voter abstains when `bundle.funding` is None (`test_funding_fade_abstains_without_data`); no positioning/basis legs referenced.
- **Spec §4.2 (decision & confidence)** → `aggregate` + `_regime_factor`; `confidence ≤ 1` locked by `test_confidence_never_exceeds_one`.
- **Spec §4.3 (risk notes, invalidation, timeframe)** → `evaluate_baseline` builds `risk_notes`/`invalidation`/`timeframe`; arithmetic locked by `test_strong_uptrend...` and `test_short_invalidation_sits_above_price`.
- **Spec §5 (honesty guardrails)** → `tier="baseline"`, the `_NO_CLAIM` label in `reason` and `risk_notes`, status never validated; label presence asserted in Task 4 and Task 5 tests.
- **Spec §5 (no auto-promote) / §6 (staging path)** → baseline writes only journal rows with `status="baseline"`; the unchanged `forward_report`/promotion path is untouched (no edits to `spec.py`, `ladder.py`, lockbox).
- **Spec §7 (testing)** → Task 2/3/4 unit tests (network-free, synthetic) + Task 5 CLI integration (monkeypatched bundle) + Task 6 regression sweep.
- **Naming consistency:** `trend_breakout_vote`, `trend_confirm_vote`, `funding_fade_vote`, `vol_rank`, `aggregate`, `BaselineConfig`, `load_baseline_config`, `baseline_hash`, `evaluate_baseline`, `_emit_baseline` used identically across all tasks.
```
