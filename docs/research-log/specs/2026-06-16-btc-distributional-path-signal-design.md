# BTC Distributional Path Signal — Research Program Design

- **Date:** 2026-06-16
- **Status:** Design approved; pre-registration and implementation pending
- **Supersedes scope of:** the handcrafted futures-signal program (price, funding, OI,
  positioning, orderbook, taker flow), now closed as having produced no robust transferable
  edge on the frozen 16-asset 4h universe (`docs/findings/PROGRAM_CONCLUSION.md`,
  `docs/findings/BACKLOG.md`).

## 0. Premise

Assume the prior program's conclusions are valid. Its single replicated finding is precise:

> **Positive fixed-horizon drift exists across every family, but no bounded-risk exit harvests
> it within the drawdown budget. The drawdown wall is structural to single-asset directional
> exposure and signal-independent.**

The prior program never failed to find *direction*. It failed to find a bounded-risk *path*.
`funding_fade` held to a fixed horizon was +1.63R/trade (+111R over 68 trades) while the same
signal incurred −100R to −277R of adverse excursion getting there. Every family told the same
story across both timeframes.

That is the strongest available evidence that **the limiting factor was the framework, not the
data**. A signal-family is a single threshold event → fixed entry → fixed exit. It models
terminal direction and is structurally blind to the *path* and to *where in a move the entry
sits*. The missing model is of the **path/risk distribution**, not the direction.

This program tests that thesis directly, on the **existing free data**, before any new-data
expansion. If it fails cleanly, the thesis is falsified on existing data and the standing
recommendation becomes new-data expansion as a *separate* pre-registered program.

## 1. Objective

A deployable signal engine that emits **LONG / SHORT / WAIT** recommendations for BTC perpetual
futures with **positive risk-adjusted expectancy**. The goal is a tradeable edge, not statistical
significance.

## 2. Scoping decisions (frozen)

| Axis | Decision |
|---|---|
| **Data boundary** | Re-extract the existing free, locally-cached series first (1h/4h/1d/1w OHLCV, funding, OI/long-short/taker metrics, book-depth). New data sources are deferred to a separate program, unlocked only by a clean kill of this one. |
| **Risk frame** | Judge under **both** frames: risk-adjusted with continuous conviction-scaled sizing (MAR/Sharpe + a hard ruin constraint) is **primary**; the prior fixed absolute −15R drawdown cap is **also reported** for cross-program comparability. |
| **Model class** | Learned probabilistic models (gradient-boosted quantile/probabilistic heads) under strict point-in-time features and nested, purged, embargoed cross-validation. |
| **Cadence / horizon** | Decide each **4h bar**; predict the forward path over **h ∈ {6, 12} bars** (~1–2 days). Cross-sectional features from the perp universe are inputs; BTC is the only deployment target. |

## 3. Architecture

### 3.1 The hypothesis (rung 2, "A")

A learned model ingests, at each 4h bar `t`, a frozen point-in-time feature vector and outputs a
**predictive distribution of the forward path** over each horizon h:

- `P(up)` — probability terminal return > 0
- `E[MFE]` — expected maximum favorable excursion
- `E[MAE]` — expected maximum adverse excursion
- return quantiles (for sizing and the ruin constraint)

The trade decision is driven by the **asymmetry** of that distribution, not a point estimate.
The model is trained to predict the very adverse excursion that killed the prior program; the
entry gate consumes `E[MAE]` directly. This is the literal embodiment of "model the path, not
the direction."

### 3.2 The scientific ladder (bias-control spine)

```
rung 0: raw existing signals          (known: drift exists, no harvestable path)
rung 1: B — regime-weighted ensemble  (baseline A must beat)
rung 2: A — distributional path model (the hypothesis)
rung 3: C — sequence model            (optional, gated)
```

- **Rung 1 (B)** reuses the existing signal families as base learners; a multi-timeframe
  state/regime classifier weights them via a meta-model. B is the **honest control**: if A
  cannot beat B, then ensembling + regime explains any gain, not path-modeling.
- **Rung 3 (C)** — an end-to-end sequence model (TCN / small transformer) — is **deferred**
  behind a promotion gate: built only if A's tree-based version clears the gate *and* leaves
  capacity-limited residual signal.

Each rung must (a) **beat the rung below it on identical folds** and (b) **clear the absolute
lockbox/DSR gate**. This two-part test makes any edge *attributable to path-modeling* rather
than to ensembling, regime, or model capacity.

### 3.3 Feature set (frozen list, computed strictly from bars ≤ t)

- Multi-TF price/vol state: 1h/4h/1d/1w returns, realized volatility, trend/range descriptors.
- Funding: level and slope.
- Positioning: OI and taker-flow z-scores from the Binance Vision metrics archive.
- Cross-sectional: BTC's funding / OI / return **rank** within the ~20-perp universe.

No feature added after the first fit. Additions require a version bump and a fresh lockbox.

## 4. Validation protocol (bias control)

- **Pre-registration.** A `PREREGISTRATION.md` freezes — before any model fit — the label
  definition, the full feature list, the model class and the complete hyperparameter grid, the
  universe/time split, and the sealed lockbox boundary. Mirrors the prior program's discipline.
- **Nested, purged, embargoed walk-forward.** Outer anchored walk-forward folds judge OOS; an
  inner CV *inside each training block* selects hyperparameters and never touches OOS. Because
  labels span 6–12 bars, train/test boundaries are **purged + embargoed** (López de Prado) so
  overlapping-horizon leakage cannot inflate scores.
- **Deflated Sharpe ≥ 0.95**, lineage-deflated, reusing the existing `deflated_sharpe` gate
  (`src/moonface/research/metrics.py`). **The trial count fed into the deflation = every
  hyperparameter combination × every rung evaluated.** This is the single most important
  anti-overfit rule for learned models.
- **One-touch lockbox tail.** The final ~20% of the window is sealed and opened exactly once,
  at the very end. If A clears OOS but the tail contradicts, the tail wins. (The same gate
  flagged `mom_30`'s −91.6% sealed-tail drawdown.)
- **Cost model** applied to the *sized* strategy: taker fees + actual funding accrual + a
  slippage charge — the realism that made the book-depth h=1 effect vanish at 10× under cost.
- **Attribution.** A's metrics are reported head-to-head against rung-1 and rung-0 on identical
  folds. An edge that does not exceed B is treated as ensembling/regime, not path-modeling.

## 5. Success / failure / termination criteria

- **Success:** A clears DSR ≥ 0.95 OOS **and** the sealed lockbox tail ratifies (positive
  risk-adjusted return, drawdown inside the ruin constraint) **and** A beats B beats rung-0 on
  identical folds. Reported under both risk frames.
- **Partial / inconclusive:** clears the risk-adjusted frame but not the fixed −15R cap, or
  OOS-positive but lockbox-marginal. Recorded; rung 3 (C) unlocked *only* on capacity-limited
  residual evidence.
- **Kill:** A fails to beat B, or fails the DSR gate. Closed, no parameter rescue. A clean kill
  **falsifies "the framework was the limiting factor" on existing data** — itself the decisive
  result — and the standing recommendation becomes new-data expansion as a separate
  pre-registered program.
- **Termination budget:** rungs 0→2 are the committed budget; C is one optional gated rung. No
  open-ended search.

## 6. LONG / SHORT / WAIT translation

Per 4h bar, A emits the path distribution, mapped to an action by a decision policy:

1. Compute a **risk-adjusted edge** = predicted drift ÷ predicted adverse excursion (`E[MAE]`),
   combined with `P(up)`.
2. **WAIT is the default.** Emit LONG/SHORT only when `|edge|` exceeds a threshold *calibrated
   on training folds* to control trade frequency and cost — inheriting the existing
   participation advisor's WAIT-default stance.
3. **Size by conviction:** a fractional-Kelly-style fraction of the predicted distribution,
   hard-capped by the ruin constraint. Low conviction → small size, never a coin-flip
   full-size entry.
4. Output plugs into the existing `moonface.signal` engine, which already emits LONG/SHORT/WAIT
   with an invalidation level and sizing fraction `f`. Deployment is a new signal *source*, not
   a new output format.

## 7. Why this could survive where 58 domains did not

Every prior family modeled terminal *direction* at a threshold event and bolted on a fixed exit
blind to the path. The replicated finding — drift exists, path kills it — is precisely a
statement that *the missing model is of the path/risk, not the direction*. A only takes
positions where predicted adverse excursion is small relative to predicted drift, and sizes by
conviction. It attacks the wall instead of re-imposing a fixed stop against it. If that fails
under honest nested validation, the data — not the framework — was the limit, and that
conclusion is itself worth the program.

## 8. Out of scope (and why)

- **New data sources** (trade-level flow, options IV/skew, on-chain PIT, cross-exchange) —
  deferred; unlocked only by a clean kill of this program.
- **More single-asset entry/exit/sizing heuristic variations** — implied dead by 58 closed
  domains; zero EV.
- **Rung 3 (C) sequence model** — gated behind A clearing the gate with residual capacity.
- **LLM/autopilot self-optimization** — a hypothesis generator, never a validator (prior
  champions carried −99.93% holdout drawdown).
