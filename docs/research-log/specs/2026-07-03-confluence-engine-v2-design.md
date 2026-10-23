# Confluence Engine v2 — Design (frozen)

**Date:** 2026-07-03
**Status:** frozen once the paired plan starts implementation. Any change to a
frozen constant after that = version bump + forward paper record reset.
**Posture:** Pro-Trader-Assistant PAPER tier. Disciplined heuristic, **no
validated-edge claim** (keep v1's `NO_CLAIM` banner verbatim). Ships
`enabled=False`; enabling is human-only.

## 1. What this is (and is not)

v2 rebuilds the existing `src/moonface/signal/engine/` confluence tier around:

1. **Five independent scoring modules** (macro, structure, momentum/divergence,
   liquidity sweep, derivatives posture) that each emit points — never trades.
2. **A threshold trigger** on the aggregated score, with a breadth requirement.
3. **A 1W Macro Gating Matrix** that vetoes macro-opposed TREND setups but
   admits macro-opposed MEAN_REVERT setups under a stricter threshold and a
   counter-trend risk profile.
4. **Fixed integer weights in code** (quantum 5) — not in config, not fitted,
   no ML.

It is **not** an alpha claim. The program record says the components have no
individual edge (liqladder, funding, macro-filter and ensemble lanes all closed
negative). The engine's value proposition is selectivity, risk discipline, and
an auditable evidence trail; the forward paper record is the only test.

Evidence-driven design constraints:
- Liquidation-sweep module uses **price structure** (swing raid + reclaim),
  not liquidation/OI data as primary (OI datasource dead both directions).
- Derivatives module is **confirmation-only** (cannot trigger alone).
- The macro gate is **veto-only at the extreme** (every broader macro filter
  tested subtracted value), and every veto is journaled with its shadow score
  so the gate can be ablated from the forward record.

## 2. Two archetype scorebooks (both max 100, signed toward long +/short −)

A single additive book double-penalizes counter-trend setups (macro −20 plus a
threshold surcharge) and lets trend-structure conflict kill every bounce. So
each bar is scored on two independent books; weights are frozen module-level
constants in code.

### TREND book (breakout / continuation) — 1W..4h

| Module | Rule (direction d = ±1) | Points |
|---|---|---|
| M1 macro | 1W bias aligned with d (confirmed) | +20 (else 0; opposition is handled by the gate) |
| M2 structure | 4h close beyond Donchian-40 extreme in d | +20 |
| | 4h close on d-side of SMA-50 AND SMA-20 on d-side of SMA-50 | +10 |
| M3 momentum | 4h ROC-12 agrees with d: \|roc\| ≥ 5% → 20; ≥ 2% → 10 | up to 20 |
| M4 pullback | 1h pullback toward SMA-20 in an established d-trend (price within 0.5×ATR of SMA-20, trend side intact) | +15 |
| M5 derivatives | funding stance vs d: extreme against d → +15; neutral (10th–80th pct) → +5; crowded in d (>80th) → 0 | up to 15 |

### MEAN_REVERT book (sweep / bounce) — 1h primary

| Module | Rule (bounce direction d) | Points |
|---|---|---|
| M4 sweep | 1h bar wicks beyond the prior 20-bar extreme against d and closes back inside | +20 |
| | reclaim: next 1h close also back inside the level | +15 |
| M3 divergence | RSI-14 divergence at the swept extreme (two confirmed pivots, k=2 confirmation lag, within 40 bars) | +25 |
| M5 derivatives | funding extreme against d (crowd positioned into the sweep) | +15 |
| | OI flush ≥ 3% over the last 6h | +10 |
| M2 stretch | 1h close ≥ 2×ATR beyond SMA-50 in the direction being faded | +15 |

Scoring rules common to both books:
- Modules emit **signed** points; opposing evidence inside a book subtracts.
- `data_ok=False` (feed gap) → module contributes 0 **and** the book's max
  attainable drops by that module's weight (degraded data makes the engine
  quieter, never louder; no renormalisation).
- **Breadth:** a book may trigger only with ≥ 3 modules non-zero in the signal
  direction.
- **Staleness:** event-type scores (sweep, reclaim, divergence) are valid on
  the confirming bar plus 2 more bars, then expire.
- Only **closed** bars on every timeframe; weekly candles are Monday-00:00-UTC
  anchored; partial groups dropped.

### Thresholds & tiers

| | trigger | Tier B | Tier A |
|---|---|---|---|
| TREND (gate=ALLOW) | ≥ 60 | 60–74 | ≥ 75 |
| MEAN_REVERT, macro not opposed | ≥ 60 | 60–74 | ≥ 75 |
| MEAN_REVERT, macro opposed (ALLOW_CT) | ≥ 70 | 70–84 | ≥ 85 |

Book arbitration: each book independently produces a candidate (passes gate,
threshold, breadth). Same direction → keep the higher score. Opposite
directions → WAIT("books conflict"). None → WAIT with score detail.

## 3. Macro bias (1W) and the Gating Matrix

`MacroState.bias ∈ {BULL, BEAR, NEUTRAL}`: last **closed** 1W candle vs the
30-week SMA of weekly closes. Hysteresis: a flip needs **2 consecutive weekly
closes** across the MA; until confirmed the effective bias is NEUTRAL.
`vol_state` reuses the v1 4h classifier (extreme vol → engine stands flat).

```
GATE[(macro, archetype, direction)]:
  (BEAR, TREND,       LONG)  -> REJECT      # never buy breakouts into a bear macro
  (BEAR, MEAN_REVERT, LONG)  -> ALLOW_CT    # counter-trend bounce, threshold 70, CT risk profile
  (BEAR, TREND,       SHORT) -> ALLOW
  (BEAR, MEAN_REVERT, SHORT) -> ALLOW
  (BULL, ·, ·)               -> mirror of BEAR
  (NEUTRAL, ·, ·)            -> ALLOW       # macro scores 0, no veto
```

Every REJECT is journaled as a WAIT with `veto` and `shadow_score` so the
forward record supports a gate ablation (what the gate cost/saved).

## 4. Risk profiles & sizing (lookup, not formula)

| | Tier A | Tier B |
|---|---|---|
| WITH_TREND | risk 1.0% (fraction 0.010); stop 2.0×ATR; 3.0×ATR trail; 96-bar time stop | 0.5% (0.005); same exits |
| COUNTER_TREND | 0.75% (0.0075); stop 1.5×ATR beyond the sweep wick; fixed 2R target; 24-bar time stop; **no trail, no adds** | 0.5% (0.005); same exits |

High-vol regime halves the fraction (v1 damp). The v1 layered discipline
kill-switch (15R/90d windowed pause, 30R hard latch, post-loss cooldown) sits
above all of this, unchanged.

## 5. Output — SetupCard

Every decision (including WAIT and vetoes) journals: engine version hash, book
scores per module with evidence strings, macro state, gate policy, breadth,
tier, risk profile, entry/stop/target plan, discipline state. The human-facing
card renders the same fields; every field needed to disagree with the machine
is on the card.

## 6. Anti-overfitting enforcement

- Weights/thresholds/gate table are frozen **constants in code**, excluded
  from `EngineConfig` so they cannot drift via config. `ENGINE_VERSION` is
  folded into `engine_hash`; any constant change = new version = the journal's
  paper record restarts from zero.
- No backtest-driven weight selection. The only permitted calibration is
  feasibility (modules fire at sane frequency on history) — magnitudes stay
  as specified here.
- Evaluation is **forward paper only**: pre-registered horizon 6 months or
  ≥ 30 setups (whichever later), success bar practical (net R > 0, MaxDD
  within the discipline budget, CT and WT sub-books separately non-negative),
  no DSR gate. Registration doc is human-frozen before enabling.

## 7. Component map (modify v1 in place; hash isolates journal records)

| v2 piece | Location |
|---|---|
| generic closed-bar resampler (4h/1d/1w) | `signal/engine/resample.py` |
| MacroState + hysteresis | `signal/engine/macro.py` (new) |
| ModuleScore contract + scorers | `signal/engine/modules/` (new pkg; ports v1 `signals.py`) |
| DerivSnapshot + feed adapter | `signal/engine/deriv.py` (new) |
| gate + two-book aggregator | `signal/engine/confluence.py` (rewrite) |
| CT risk profile + tier sizing | `signal/engine/position.py`, `discipline.py` |
| orchestration + SetupCard | `signal/engine/engine.py`, `signal/engine/setupcard.py` (new) |
| config v2 (operational params only) | `signal/engine/config.py` |
