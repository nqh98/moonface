# Relaxed Budget BTC V2 — Narrow Confirmatory Design Spec

- **Date:** 2026-06-10
- **Status:** Approved for implementation planning
- **Relation to prior work:** `relaxed_budget_btc` v1 closed negative with 270/270
  hypotheses rejected and no corrected survivors. V2 is a new pre-registered domain
  version. It does not mutate v1, reopen v1 verdicts, or spend v1's lockbox.

## 1. Charter

Register `relaxed_budget_btc` v2 as a narrow confirmatory BTC futures research domain
inside the existing autonomous research pipeline.

- **Optimize for:** testing whether the strongest v1 families survive strict correction
  when the trial count is reduced before any v2 result is observed.
- **Not optimized for:** maximizing backtest return or expanding discovery breadth.
- **Scope:** domain registration and validation through the existing research ladder.
- **Out of scope:** new signal generators, new data sources, live trading, order execution,
  threshold tuning after v2 is registered, and any changes to v1 rows or reports.

## 2. Rationale

V1 produced no corrected survivor because its 270-hypothesis grid made the Stage-3 DSR
gate hard to clear. Several rejected rows still showed useful research-window behavior,
especially in:

- `basis_discount_reversion {"window": 180, "pct": 5}`
- `funding_fade {"window": 180, "z_thr": 2.0}`

V2 tests only these pre-selected families with a small exit set and a single sizing
fraction. The resulting full grid has six hypotheses, making the multiple-comparisons
penalty honest but less dominated by exploratory breadth.

## 3. Pre-Registered Grid

Domain identity:

- `name`: `relaxed_budget_btc`
- `version`: `2`
- `asset`: BTC perpetual, 4h, same asset metadata as v1
- `judging_metric`: MAR
- `grid_size`: 6

Asset record:

```python
{
    "exchange": "binance",
    "symbol": "BTC/USDT:USDT",
    "timeframe": "4h",
    "funding_symbol": "BTC/USDT:USDT",
    "spot_symbol": "BTC/USDT",
}
```

Entries:

```python
[
    ("basis_discount_reversion", {"window": 180, "pct": 5}),
    ("funding_fade", {"window": 180, "z_thr": 2.0}),
]
```

Exits:

```python
[
    ("fixed_bracket", {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}),
    ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0}),
    ("atr_trail", {"atr_period": 14, "k_trail": 3.0, "max_bars": 48}),
]
```

Sizing:

```python
[0.01]
```

The grid is the cartesian product of entries, exits, and sizing fractions. Hypothesis
hashes remain the existing SHA-256 of canonical spec JSON.

## 4. Validation Gates

V2 uses the existing pipeline stages and thresholds without tuning:

| Stage | Gate |
|---|---|
| Screen | `trade_count >= 30` and `expectancy > 0` |
| Walk-forward | OOS `MAR > 0` |
| Correction | DSR confidence `>= 0.95`, trials = full v2 grid size `6` |
| Lockbox | tail `MAR >= 1.0` and tail `trade_count >= 10` |

The lockbox remains one-touch. `gate relaxed_budget_btc --version 2 --open-lockbox`
may run only after Stage 3 produces at least one corrected survivor and the domain status
is `awaiting_gate`.

## 5. Data Fence

Registering v2 freezes a new research window and fence using the existing domain
registration convention:

- `start_ms = now_ms - 3 years`
- `end_ms = now_ms`
- `fence_ts = now_ms - final 20% of the 3-year window`

The fence is stored at registration and never moves. All stages continue to access data
through the existing `FencedBundle` path.

## 6. Implementation Shape

Modify `src/moonface/research/domains.py` only enough to expose:

- `relaxed_budget_v2_grid() -> list[HypothesisSpec]`
- registration of `("relaxed_budget_btc", 2)` in the existing init path

The existing CLI can already address versions for `report` and `gate`, but `run --domain`
selects by domain name. Because v1 is terminal, adding v2 under the same name is acceptable:
the runner skips closed v1 and processes active v2.

Do not add a new CLI command for v2. `python tools/research.py init` should idempotently
insert v2 when it is missing and leave it unchanged once registered.

## 7. Testing

Add focused tests for:

- v2 grid size is exactly 6
- v2 grid is deterministic
- v2 specs use `domain="relaxed_budget_btc"` and `version=2`
- v2 grid carries `funding_symbol` and `spot_symbol`
- `register_v1` remains idempotent while registering v2 for stores that do not have it
- a store that already has v1 keeps v1 unchanged and receives v2 exactly once

Existing research store, lockbox, runner, and smoke tests should continue to pass.

## 8. Success Criteria

Implementation is complete when:

- `python tools/research.py init` registers `relaxed_budget_btc v2`
- `python tools/research.py status` shows v1 terminal and v2 active with grid size 6
- focused research tests pass
- no v1 hypothesis rows, v1 reports, or v1 domain metadata are modified by code changes
