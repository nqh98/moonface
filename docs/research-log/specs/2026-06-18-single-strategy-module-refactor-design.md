# Single-Strategy Module Refactor and Optimization Boundary

**Date:** 2026-06-18  
**Status:** Approved design  
**Scope:** Refactor the real-time signal runtime to load one configured strategy
through a stable interface. Preserve the watcher, journal, and Telegram behavior.
Optimization remains a separate follow-up phase.

## Goal

Make each strategy an isolated module while retaining one active configured
strategy. The same strategy implementation must be usable by both real-time
paper monitoring and research, preventing research/runtime logic drift.

This refactor must not alter the current Donchian strategy's decisions,
configuration identity, journal entries, watch cadence, or notification path.

## Current State

`promotion/strategy.json` describes a promoted strategy with:

- an entry family and parameters;
- an exit name and parameters;
- an asset and timeframe;
- a paper/live status and risk fraction;
- research provenance and a drawdown limit.

`signal.evaluate.evaluate()` currently contains generic orchestration and
strategy-specific assumptions in one function. `signal.cli` separately handles
data loading, scheduling, journaling, reporting, and alerts. Telegram delivery is
already isolated in `signal.notify`.

The current promoted strategy is the long-only BTCUSDT 4h Donchian 40/20
strategy in paper status.

## Scope Boundaries

### Included

- One configured strategy active at a time.
- A small, static registry of supported strategy modules.
- A common strategy-module contract.
- Extraction of Donchian evaluation into its own module.
- Backward compatibility for `promotion/strategy.json`.
- Preservation of strategy hashing and existing journal continuity.
- Contract and parity tests across config loading, evaluation, CLI watch, and
  notifications.
- A documented extension point for later strategies.

### Excluded

- Multiple strategies running concurrently.
- Signal arbitration, portfolio allocation, or cross-strategy risk aggregation.
- Dynamic import paths or third-party plugins.
- Exchange order execution.
- Changes to Telegram transport or credentials.
- Parameter optimization inside this refactor.
- Automatic promotion of optimized parameters.

## Architecture

### Strategy contract

Create `moonface.signal.strategies` with a deliberately small contract:

```python
class StrategyModule(Protocol):
    family: str

    def validate(self, strategy: PromotedStrategy) -> bool:
        ...

    def evaluate(
        self,
        strategy: PromotedStrategy,
        bundle: DataBundle,
    ) -> Signal:
        ...
```

The module owns validation and latest-candle signal evaluation for its family.
It returns the existing `Signal` value object. It does not fetch data, write the
journal, format console output, schedule evaluations, or send notifications.

The initial implementation is:

```text
signal/strategies/donchian.py
```

It owns Donchian-specific entry evaluation and invalidation calculation. It
reuses the existing research primitives rather than duplicating channel or risk
math.

### Static registry

Create a registry in `signal/strategies/__init__.py`:

```python
STRATEGIES = {
    "donchian_break": DONCHIAN,
}
```

The registry is explicit and code-reviewed. Configuration cannot provide an
arbitrary Python import path. Unsupported families fail closed during
`load_strategy()`.

### Generic dispatcher

`signal.evaluate.evaluate()` remains the public entry point for compatibility,
but becomes a thin dispatcher:

1. resolve `strategy.family` from the registry;
2. fail closed with a `WAIT` signal if no implementation exists;
3. delegate evaluation to the selected strategy module.

Existing callers do not need to change.

### Configuration compatibility

The current JSON shape remains valid:

```json
{
  "family": "donchian_break",
  "params": {"n": 40, "long_only": true},
  "exit": {
    "name": "donchian_trail",
    "params": {"atr_period": 14, "k_stop": 2.0, "trail_n": 20}
  }
}
```

`family` is the registry key. No new `module`, `class`, or import-path field is
introduced.

`strategy_hash()` remains based on the same signal-relevant JSON fields. Moving
implementation code must not start a new forward-journal segment.

### Runtime boundaries

The runtime remains:

```text
strategy.json
    -> load_strategy()
    -> registry validation
    -> CLI loads fresh closed-candle data
    -> evaluate() dispatches to Donchian module
    -> Signal
    -> existing journal / console formatting / forward gate
    -> existing _alert()
    -> existing TelegramNotifier
```

The following modules retain their responsibilities and should not require
behavioral changes:

- `signal/cli.py`: command handling, watch loop, data orchestration, output,
  journal calls, and alert calls;
- `signal/journal.py`: persistence and forward-gate reporting;
- `signal/notify.py`: Telegram transport;
- `signal/spec.py`: configuration loading and strategy identity.

`spec.py` changes only enough to ask the strategy registry to validate the
strategy-specific fields.

## Donchian Module

The Donchian module must preserve current behavior:

- evaluate only the final closed candle;
- use the sentinel extension required by research entry generators;
- call the existing `generate_entries("donchian_break", params, bundle)` path;
- select the last matching side for the final candle;
- derive initial invalidation from the configured ATR period and stop multiple;
- return `WAIT` for insufficient history, no current entry, or undefined ATR;
- retain existing reason text unless a test demonstrates that a more stable
  equivalent is necessary.

Generic sentinel construction may live in a small internal helper if another
strategy would need it, but no framework should be built speculatively.

## Failure Handling

- Missing, malformed, or unsupported configuration: `load_strategy()` returns
  `None`, preserving the existing fallback behavior.
- A registered module rejecting its configuration: `load_strategy()` returns
  `None`.
- Insufficient market history or undefined indicators: module returns `WAIT`.
- Data-fetch failures: existing `DataError` alert and retry behavior remains.
- Telegram failure: existing notifier logs the failure and never terminates the
  watcher.
- Strategy implementation exceptions are not silently converted to `WAIT`.
  They remain visible failures during one-shot execution; watch-mode resilience
  should only catch explicitly classified data errors. This avoids hiding code
  defects as market decisions.

## Testing

### Registry and configuration

- Registered Donchian configuration loads successfully.
- Unknown family fails closed.
- Invalid Donchian parameters fail closed.
- Existing `promotion/strategy.json` remains valid.
- Strategy hash is unchanged for an equivalent configuration before and after
  extraction.

### Donchian parity

Move or duplicate the existing evaluator tests at the module boundary:

- no candles / insufficient candles returns `WAIT`;
- no final-bar breakout returns `WAIT`;
- final-bar long breakout returns the same decision, price, invalidation,
  fraction, and reason as before;
- long-only behavior remains intact;
- ATR-unavailable behavior remains intact.

A characterization test should capture the old evaluator result before the
dispatcher is introduced, then assert the extracted module produces the same
`Signal`.

### Dispatcher

- `evaluate()` resolves Donchian from the registry and delegates once.
- An unresolved family fails closed.

### End-to-end runtime

Existing CLI and notifier tests remain green. Add one focused contract test:

```text
configured Donchian
  -> watcher evaluates one closed candle
  -> one journal entry
  -> existing notifier receives the existing alert shape
```

No Telegram implementation test needs to change unless imports move.

## Research and Optimization Follow-up

Optimization starts only after extraction parity and the full test suite pass.
It is a separate specification and plan because it changes experimental
behavior rather than architecture.

The follow-up must:

1. use the same Donchian strategy primitives consumed by the strategy module;
2. freeze an intentionally small parameter search before running it;
3. evaluate only untouched walk-forward test windows after realistic fees,
   slippage, and funding;
4. compare the candidate against the current 40/20 paper baseline, not merely
   against zero;
5. require improvement across multiple windows rather than one favorable era;
6. write a new result artifact and configuration candidate;
7. leave `promotion/strategy.json` unchanged until a human approves promotion;
8. start a new journal identity only when signal-relevant parameters actually
   change.

The current paper watcher continues running from the release branch while
research proceeds on a separate research branch or worktree.

## Branch Model

After the refactor passes verification:

- create a release branch from the verified refactor commit for continuous
  paper monitoring;
- keep `promotion/strategy.json` at `"status": "paper"`;
- conduct optimization on a separate branch/worktree;
- merge only validated architecture fixes into the release branch;
- promote changed strategy parameters through an explicit reviewed commit.

The existing dirty working-tree changes must be classified and committed or
excluded before branch creation. Generated `egg-info` changes should not be
mixed into the strategy refactor unless packaging metadata is intentionally
regenerated.

## Acceptance Criteria

- One configured strategy is resolved through a static registry.
- Donchian implementation lives in its own strategy module.
- Existing configuration loads without migration.
- Existing strategy hash and journal continuity are preserved.
- Existing Donchian decisions are unchanged on characterization fixtures.
- Watch scheduling, journaling, forward reporting, and Telegram behavior remain
  unchanged.
- Unknown or invalid strategy configuration fails closed.
- Targeted tests, full tests, and lint pass before a release branch is created.
- Optimization is not mixed into the behavior-preserving refactor.
