# Single-Strategy Module Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Donchian signal evaluation behind a static, single-strategy registry without changing configuration, signal decisions, journal identity, watch behavior, or Telegram delivery.

**Architecture:** Add a small `signal.strategies` package containing a typed strategy contract, a static registry, and the Donchian implementation. Keep `signal.evaluate.evaluate()` as the compatible public dispatcher and make `signal.spec.load_strategy()` delegate strategy-specific validation to the registry. The CLI, journal, and notifier remain behaviorally unchanged.

**Tech Stack:** Python 3.12, dataclasses, typing `Protocol`, pytest, ruff, existing MoonFace research and risk primitives.

---

## Constraints

- Preserve the current `promotion/strategy.json` schema.
- Preserve the exact `strategy_hash()` payload and existing journal identity.
- Support exactly one configured strategy.
- Do not introduce dynamic imports or a plugin framework.
- Do not modify `src/moonface/signal/notify.py`.
- Do not optimize parameters in this plan.
- Preserve unrelated working-tree changes.
- Use `rtk` for shell commands.

## File Structure

| File | Responsibility |
|---|---|
| `src/moonface/signal/strategies/base.py` | `StrategyModule` protocol only. |
| `src/moonface/signal/strategies/donchian.py` | Validate and evaluate Donchian configuration. |
| `src/moonface/signal/strategies/__init__.py` | Static registry and lookup helpers. |
| `src/moonface/signal/evaluate.py` | Existing `Signal` type plus thin registry dispatcher. |
| `src/moonface/signal/spec.py` | Generic config validation plus registry validation. |
| `tests/test_signal_strategy_donchian.py` | Donchian module characterization and validation tests. |
| `tests/test_signal_strategy_registry.py` | Registry and dispatcher tests. |
| `tests/test_signal_spec.py` | Backward compatibility and hash-continuity tests. |
| `tests/test_signal_cli.py` | One end-to-end configured strategy/watch/notifier contract test. |

### Task 1: Characterize Existing Donchian Behavior

**Files:**
- Create: `tests/test_signal_strategy_donchian.py`
- Read: `src/moonface/signal/evaluate.py`
- Read: `tests/test_signal_evaluate.py`

- [ ] **Step 1: Add characterization fixtures and expected outputs**

```python
from dataclasses import replace

from moonface.research.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.research.synth import make_candles
from moonface.signal.evaluate import evaluate
from moonface.signal.spec import PromotedStrategy


STRATEGY = PromotedStrategy(
    family="donchian_break",
    params={"n": 20},
    exit={
        "name": "fixed_bracket",
        "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0},
    },
    fraction=0.01,
    status="paper",
    asset={
        "exchange": "binance",
        "symbol": "BTC/USDT:USDT",
        "timeframe": "4h",
    },
    provenance={},
    max_drawdown_p95=0.2,
)


def _entry_case():
    candles = make_candles(400)
    i, side = generate_entries(
        "donchian_break", STRATEGY.params, DataBundle(candles=candles)
    )[-1]
    return candles, i, side


def test_current_donchian_entry_characterization():
    candles, i, side = _entry_case()
    signal = evaluate(STRATEGY, DataBundle(candles=candles[: i + 1]))
    assert signal.decision == side
    assert signal.price == candles[i].close
    assert signal.fraction == 0.01
    assert signal.reason == f"donchian_break {{'n': 20}} fired {side}"


def test_current_donchian_quiet_bar_characterization():
    candles = make_candles(400)
    entry_indexes = {
        i for i, _ in generate_entries(
            "donchian_break", STRATEGY.params, DataBundle(candles=candles)
        )
    }
    quiet = next(i for i in range(100, 399) if i not in entry_indexes)
    signal = evaluate(STRATEGY, DataBundle(candles=candles[: quiet + 1]))
    assert signal.decision == "WAIT"
    assert signal.reason == "no donchian_break entry on the last closed candle"


def test_current_donchian_long_only_characterization():
    strategy = replace(STRATEGY, params={"n": 20, "long_only": True})
    candles = make_candles(400)
    entries = generate_entries(
        "donchian_break", strategy.params, DataBundle(candles=candles)
    )
    assert all(side == "LONG" for _, side in entries)
```

- [ ] **Step 2: Run the characterization tests**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_donchian.py
```

Expected: PASS. These tests freeze current behavior before extraction.

- [ ] **Step 3: Commit the characterization tests**

```bash
rtk git add tests/test_signal_strategy_donchian.py
rtk git diff --cached --stat
rtk git commit -m "test(signal): characterize Donchian runtime behavior"
```

### Task 2: Add the Strategy Contract and Static Registry

**Files:**
- Create: `src/moonface/signal/strategies/base.py`
- Create: `src/moonface/signal/strategies/__init__.py`
- Create: `tests/test_signal_strategy_registry.py`

- [ ] **Step 1: Write failing registry tests**

```python
from moonface.signal.strategies import get_strategy_module, supports_strategy


def test_registry_resolves_donchian():
    module = get_strategy_module("donchian_break")
    assert module is not None
    assert module.family == "donchian_break"


def test_registry_rejects_unknown_family():
    assert get_strategy_module("astrology") is None
    assert supports_strategy("astrology") is False
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_registry.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'moonface.signal.strategies'`.

- [ ] **Step 3: Add the protocol**

Create `src/moonface/signal/strategies/base.py`:

```python
from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from moonface.research.bundle import DataBundle
    from moonface.signal.evaluate import Signal
    from moonface.signal.spec import PromotedStrategy


class StrategyModule(Protocol):
    family: str

    def validate(self, strategy: PromotedStrategy) -> bool:
        ...

    def evaluate(
        self, strategy: PromotedStrategy, bundle: DataBundle
    ) -> Signal:
        ...
```

- [ ] **Step 4: Add an explicit registry with a temporary Donchian placeholder**

Create `src/moonface/signal/strategies/__init__.py`:

```python
from __future__ import annotations

from moonface.signal.strategies.base import StrategyModule


class _PendingDonchian:
    family = "donchian_break"

    def validate(self, strategy) -> bool:
        return False

    def evaluate(self, strategy, bundle):
        raise NotImplementedError


STRATEGIES: dict[str, StrategyModule] = {
    "donchian_break": _PendingDonchian(),
}


def get_strategy_module(family: str) -> StrategyModule | None:
    return STRATEGIES.get(family)


def supports_strategy(family: str) -> bool:
    return family in STRATEGIES
```

- [ ] **Step 5: Run registry tests and lint**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_registry.py
rtk ruff check src/moonface/signal/strategies tests/test_signal_strategy_registry.py
```

Expected: PASS.

- [ ] **Step 6: Commit the contract and registry**

```bash
rtk git add src/moonface/signal/strategies tests/test_signal_strategy_registry.py
rtk git diff --cached --stat
rtk git commit -m "feat(signal): add static strategy registry contract"
```

### Task 3: Extract Donchian Validation and Evaluation

**Files:**
- Create: `src/moonface/signal/strategies/donchian.py`
- Modify: `src/moonface/signal/strategies/__init__.py`
- Modify: `tests/test_signal_strategy_donchian.py`

- [ ] **Step 1: Add failing Donchian module tests**

Append to `tests/test_signal_strategy_donchian.py`:

```python
from moonface.signal.strategies.donchian import DONCHIAN


def test_donchian_module_accepts_current_configuration():
    assert DONCHIAN.validate(STRATEGY) is True


def test_donchian_module_rejects_invalid_parameters():
    assert DONCHIAN.validate(replace(STRATEGY, params={"n": 1})) is False
    assert DONCHIAN.validate(
        replace(
            STRATEGY,
            exit={"name": "fixed_bracket", "params": {"k_stop": 1.0}},
        )
    ) is False


def test_extracted_module_matches_characterized_entry():
    candles, i, _side = _entry_case()
    bundle = DataBundle(candles=candles[: i + 1])
    assert DONCHIAN.evaluate(STRATEGY, bundle) == evaluate(STRATEGY, bundle)
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_donchian.py
```

Expected: FAIL because `moonface.signal.strategies.donchian` does not exist.

- [ ] **Step 3: Implement the Donchian module**

Create `src/moonface/signal/strategies/donchian.py`:

```python
from __future__ import annotations

from moonface.models import Candle
from moonface.research.bundle import DataBundle
from moonface.research.entries import generate_entries


def _wait(reason: str):
    from moonface.signal.evaluate import Signal

    return Signal("WAIT", None, None, None, reason)


def _sentinel_extended(bundle: DataBundle) -> DataBundle:
    last = bundle.candles[-1]
    tf_ms = bundle.candles[1].timestamp_ms - bundle.candles[0].timestamp_ms
    sentinel = Candle(
        last.timestamp_ms + tf_ms,
        last.close,
        last.close,
        last.close,
        last.close,
        0.0,
    )

    def extend(series):
        return None if series is None else list(series) + [None]

    return DataBundle(
        candles=list(bundle.candles) + [sentinel],
        funding=extend(bundle.funding),
        basis=extend(bundle.basis),
        feature=extend(bundle.feature),
    )


class DonchianStrategy:
    family = "donchian_break"

    def validate(self, strategy) -> bool:
        params = strategy.params
        exit_params = strategy.exit.get("params")
        return (
            isinstance(params.get("n"), int)
            and params["n"] >= 2
            and isinstance(params.get("long_only", False), bool)
            and isinstance(exit_params, dict)
            and isinstance(exit_params.get("atr_period"), int)
            and exit_params["atr_period"] > 0
            and isinstance(
                exit_params.get("k_stop", exit_params.get("k_trail", 1.0)),
                (int, float),
            )
        )

    def evaluate(self, strategy, bundle: DataBundle):
        from moonface.backtest.edge.evaluate import _risk
        from moonface.signal.evaluate import Signal

        if len(bundle.candles) < 2:
            return _wait("not enough closed candles")
        last_index = len(bundle.candles) - 1
        extended = _sentinel_extended(bundle)
        entries = generate_entries(self.family, strategy.params, extended)
        sides = [side for i, side in entries if i == last_index]
        if not sides:
            return _wait(
                "no donchian_break entry on the last closed candle"
            )
        side = sides[-1]
        params = strategy.exit["params"]
        k = params.get("k_stop") or params.get("k_trail") or 1.0
        unit = _risk(
            extended.candles, last_index, k, params["atr_period"]
        )
        if unit is None:
            return _wait("ATR risk unit undefined on this window")
        price = bundle.candles[last_index].close
        invalidation = price - unit if side == "LONG" else price + unit
        return Signal(
            side,
            price,
            round(invalidation, 2),
            strategy.fraction,
            f"{self.family} {strategy.params} fired {side}",
        )


DONCHIAN = DonchianStrategy()
```

- [ ] **Step 4: Replace the registry placeholder**

Replace `src/moonface/signal/strategies/__init__.py` with:

```python
from __future__ import annotations

from moonface.signal.strategies.base import StrategyModule
from moonface.signal.strategies.donchian import DONCHIAN


STRATEGIES: dict[str, StrategyModule] = {
    DONCHIAN.family: DONCHIAN,
}


def get_strategy_module(family: str) -> StrategyModule | None:
    return STRATEGIES.get(family)


def supports_strategy(family: str) -> bool:
    return family in STRATEGIES
```

- [ ] **Step 5: Run module and registry tests**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_donchian.py tests/test_signal_strategy_registry.py
rtk ruff check src/moonface/signal/strategies tests/test_signal_strategy_donchian.py tests/test_signal_strategy_registry.py
```

Expected: PASS.

- [ ] **Step 6: Commit the Donchian module**

```bash
rtk git add src/moonface/signal/strategies tests/test_signal_strategy_donchian.py
rtk git diff --cached --stat
rtk git commit -m "refactor(signal): extract Donchian strategy module"
```

### Task 4: Convert the Public Evaluator to a Dispatcher

**Files:**
- Modify: `src/moonface/signal/evaluate.py`
- Modify: `tests/test_signal_strategy_registry.py`
- Test: `tests/test_signal_evaluate.py`

- [ ] **Step 1: Add failing delegation tests**

Append to `tests/test_signal_strategy_registry.py`:

```python
from moonface.research.bundle import DataBundle
from moonface.research.synth import make_candles
from moonface.signal import evaluate as evaluate_module
from moonface.signal.evaluate import Signal
from tests.test_signal_evaluate import STRATEGY


def test_public_evaluate_delegates_to_registered_module(monkeypatch):
    expected = Signal("WAIT", None, None, None, "delegated")

    class FakeModule:
        family = "donchian_break"

        def validate(self, strategy):
            return True

        def evaluate(self, strategy, bundle):
            return expected

    monkeypatch.setattr(
        evaluate_module, "get_strategy_module", lambda family: FakeModule()
    )
    bundle = DataBundle(candles=make_candles(3))
    assert evaluate_module.evaluate(STRATEGY, bundle) == expected


def test_public_evaluate_fails_closed_for_unregistered_family(monkeypatch):
    monkeypatch.setattr(
        evaluate_module, "get_strategy_module", lambda family: None
    )
    bundle = DataBundle(candles=make_candles(3))
    signal = evaluate_module.evaluate(STRATEGY, bundle)
    assert signal.decision == "WAIT"
    assert signal.reason == "unsupported strategy family: donchian_break"
```

- [ ] **Step 2: Verify the delegation test fails**

Run:

```bash
rtk pytest -q tests/test_signal_strategy_registry.py
```

Expected: FAIL because `evaluate.py` does not expose or use
`get_strategy_module`.

- [ ] **Step 3: Reduce `evaluate.py` to the compatible dispatcher**

Keep the existing `Signal` dataclass and replace the old sentinel/evaluation
implementation with:

```python
from moonface.research.bundle import DataBundle
from moonface.signal.spec import PromotedStrategy
from moonface.signal.strategies import get_strategy_module


def _wait(reason: str) -> Signal:
    return Signal("WAIT", None, None, None, reason)


def evaluate(strategy: PromotedStrategy, bundle: DataBundle) -> Signal:
    module = get_strategy_module(strategy.family)
    if module is None:
        return _wait(f"unsupported strategy family: {strategy.family}")
    return module.evaluate(strategy, bundle)
```

Remove imports and helpers no longer used by the dispatcher.

- [ ] **Step 4: Run parity and dispatcher tests**

Run:

```bash
rtk pytest -q tests/test_signal_evaluate.py tests/test_signal_strategy_donchian.py tests/test_signal_strategy_registry.py
rtk ruff check src/moonface/signal/evaluate.py src/moonface/signal/strategies tests/test_signal_evaluate.py tests/test_signal_strategy_donchian.py tests/test_signal_strategy_registry.py
```

Expected: PASS with unchanged characterization outputs.

- [ ] **Step 5: Commit the dispatcher**

```bash
rtk git add src/moonface/signal/evaluate.py tests/test_signal_strategy_registry.py
rtk git diff --cached --stat
rtk git commit -m "refactor(signal): dispatch evaluation through strategy registry"
```

### Task 5: Delegate Configuration Validation to the Strategy Module

**Files:**
- Modify: `src/moonface/signal/spec.py`
- Modify: `tests/test_signal_spec.py`

- [ ] **Step 1: Add failing compatibility and validation tests**

Append to `tests/test_signal_spec.py`:

```python
from pathlib import Path


def test_invalid_donchian_params_are_none(tmp_path):
    assert load_strategy(
        _write(tmp_path, {**VALID, "params": {"n": 1}})
    ) is None


def test_repository_promoted_strategy_still_loads():
    path = Path(__file__).parents[1] / "promotion" / "strategy.json"
    strategy = load_strategy(path)
    assert strategy is not None
    assert strategy.family == "donchian_break"
    assert strategy.params == {"n": 40, "long_only": True}


def test_hash_payload_remains_backward_compatible(tmp_path):
    strategy = load_strategy(_write(tmp_path, VALID))
    expected = {
        "family": strategy.family,
        "params": strategy.params,
        "exit": strategy.exit,
        "fraction": strategy.fraction,
        "asset": strategy.asset,
    }
    text = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    import hashlib

    assert strategy_hash(strategy) == hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
```

- [ ] **Step 2: Verify invalid parameter validation fails**

Run:

```bash
rtk pytest -q tests/test_signal_spec.py
```

Expected: `test_invalid_donchian_params_are_none` FAILS because generic loading
currently accepts `n=1`.

- [ ] **Step 3: Update `load_strategy()`**

In `src/moonface/signal/spec.py`, replace the `known_families()` check with the
registry and retain generic exit validation:

```python
from moonface.signal.strategies import get_strategy_module


module = get_strategy_module(s.family)
if (
    s.status not in VALID_STATUSES
    or module is None
    or not isinstance(s.params, dict)
    or not isinstance(s.exit, dict)
    or s.exit.get("name") not in EXECUTABLE_EXITS
    or not isinstance(s.exit.get("params"), dict)
    or "atr_period" not in s.exit["params"]
    or not isinstance(s.fraction, (int, float))
    or s.fraction <= 0
    or not isinstance(s.asset, dict)
    or not isinstance(s.max_drawdown_p95, (int, float))
    or s.max_drawdown_p95 <= 0
    or not module.validate(s)
):
    return None
```

Keep `strategy_hash()` unchanged.

- [ ] **Step 4: Run specification and evaluator tests**

Run:

```bash
rtk pytest -q tests/test_signal_spec.py tests/test_signal_evaluate.py tests/test_signal_strategy_donchian.py
rtk ruff check src/moonface/signal/spec.py tests/test_signal_spec.py
```

Expected: PASS.

- [ ] **Step 5: Commit validation delegation**

```bash
rtk git add src/moonface/signal/spec.py tests/test_signal_spec.py
rtk git diff --cached --stat
rtk git commit -m "refactor(signal): validate configuration through strategy module"
```

### Task 6: Verify the Existing Watch and Telegram Contract

**Files:**
- Modify: `tests/test_signal_cli.py`
- Do not modify: `src/moonface/signal/cli.py`
- Do not modify: `src/moonface/signal/notify.py`

- [ ] **Step 1: Add an end-to-end contract test**

Append to `tests/test_signal_cli.py`:

```python
def test_configured_strategy_watch_journals_and_notifies_without_transport_changes(
    tmp_path, monkeypatch
):
    _setup_fresh(tmp_path, monkeypatch)
    sent = []

    class FakeNotifier:
        def send(self, message):
            sent.append(message)

    args = _watch_args(tmp_path)
    rc = cli.watch(
        args,
        iterations=1,
        sleep_fn=lambda seconds: None,
        notifier=FakeNotifier(),
    )

    assert rc == 0
    entries = read_entries(args.journal)
    assert len(entries) == 1
    assert entries[0]["strategy_version"]
    assert len(sent) == 1
    assert sent[0].startswith("paper signal:")
```

- [ ] **Step 2: Run signal-runtime tests**

Run:

```bash
rtk pytest -q tests/test_signal_cli.py tests/test_signal_notify.py tests/test_signal_journal.py
```

Expected: PASS without modifying CLI or notification production code.

- [ ] **Step 3: Inspect production diffs**

Run:

```bash
rtk git diff -- src/moonface/signal/cli.py src/moonface/signal/notify.py
```

Expected: no new refactor changes in either file. Existing user changes, if
present, must remain distinguishable and unmodified.

- [ ] **Step 4: Commit the contract test**

```bash
rtk git add tests/test_signal_cli.py
rtk git diff --cached --stat
rtk git commit -m "test(signal): preserve watch and notification contract"
```

### Task 7: Full Verification and Release-Branch Preparation

**Files:**
- Verify all changed files.
- Do not edit generated `src/moonface.egg-info/*`.

- [ ] **Step 1: Run targeted tests**

```bash
rtk pytest -q tests/test_signal_strategy_donchian.py tests/test_signal_strategy_registry.py tests/test_signal_evaluate.py tests/test_signal_spec.py tests/test_signal_cli.py tests/test_signal_notify.py tests/test_signal_journal.py
```

Expected: PASS.

- [ ] **Step 2: Run the full suite**

```bash
rtk pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lint**

```bash
rtk ruff check src tests tools
```

Expected: no lint errors.

- [ ] **Step 4: Review changed execution flows and working-tree boundaries**

```bash
rtk git status --short
rtk git diff --stat
rtk git log --oneline -8
```

Expected: strategy-refactor commits are isolated. Existing unrelated changes
remain uncommitted and are not overwritten.

- [ ] **Step 5: Create the release branch only from a verified clean commit**

If unrelated local changes prevent a clean branch point, create the release
branch in an isolated worktree from the final refactor commit. Use:

```bash
rtk git branch release/paper-donchian
```

Expected: `release/paper-donchian` points at the verified refactor commit and
retains `"status": "paper"`.

- [ ] **Step 6: Record the optimization handoff**

The next specification must freeze a small Donchian candidate grid, compare it
against the current 40/20 baseline on untouched walk-forward test windows, and
leave `promotion/strategy.json` unchanged until explicit approval. Do not start
that search as part of this plan.

