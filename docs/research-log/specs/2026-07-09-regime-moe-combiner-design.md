# Regime-Conditional Mixture-of-Experts (MoE) Combiner — Design Spec

**Date:** 2026-07-09
**Status:** Design spec only (no implementation plan, no code — by request)
**Scope:** Mathematical + logical framework for a regime-conditional weighted combiner over existing "weak-learner" experts, with the overfitting defense as the primary deliverable.

---

## 0. Framing — what this is, and what it is NOT

This spec formalizes a **reusable, artifact-proof MoE combiner**, not a claim of edge.

The success criterion is **not** "it makes money." It is:

> When fed dead experts or null data, the framework **correctly returns NEGATIVE**; and if a real conditional edge ever exists, it can be detected **without inflating** it.

This is the `vol-compression` lesson elevated to a design principle: *a valid gate must fail on null.*

### 0.1 Prior-art collision (stated honestly, up front)

This architecture is **not new to this codebase.** It is the soft-gated generalization of work already closed:

- **`regime-mechanism-engine-v3`** (`CLOSED_NEGATIVE_VALIDATION`, 2026-07-06) — "regime selects one specialist mechanism; score only sizes." That is a **hard-gated (top-1) MoE with a frozen regime→expert matrix.** Its `src/moonface/signal/engine/v3/matrix.py::REGIME_MECHANISM` *is* a binary weight matrix. Verdict note: *"the negative falls on the SELECTION architecture itself, not additive weighting… same structural wall."*
- **`matrix-step-a-router`** (CLOSED NEGATIVE, 2026-07-07) — regime→mode router; first overlay to descriptively beat the floor, then killed by a read-only bootstrap CI at n=36 (underpowered artifact; exact repeat of the `signal-matrix-horizon-harvest` n=8→n=106 collapse).
- Plus `portfolio-tournament` (0/8 ensembles clear DSR), `regime-selector` / `regime-overlay` (macro conditioning *subtracts*), `confluence-v2.2` (additive weighted sum — stays WAIT/paper; headline R was an artifact).

**Therefore the deliverable is scaffolding + an anti-artifact protocol.** The single most probable outcome on the current free-data expert set is that **Gate-0 (null calibration) or the power budget refuses to certify anything** — and that refusal is the framework working correctly, not a bug.

### 0.2 Relationship to existing infrastructure

The combiner is a **layer on top of the existing harness**, not a new stack. It reuses:

| Need | Existing module |
|---|---|
| Regime classification | `src/moonface/signal/engine/v3/regime.py::classify_regime` (`DirState × VolState`) |
| Hard-gate matrix (generalized here) | `src/moonface/signal/engine/v3/matrix.py::REGIME_MECHANISM` |
| Train→Gate1→Gate2→Gate3 walk-forward | `src/moonface/signal/engine/v3/evaluate.py` |
| Deflated Sharpe + trial accounting | `src/moonface/foundation/metrics.py::deflated_sharpe`, `expected_max_sharpe` |
| Overlapping-signal handling, null tooling | `src/moonface/signal/engine/calibration.py` |
| R summaries | `src/moonface/foundation/metrics.py::summarize_r` |

Frozen split convention (inherited from v3 eval): **train 2020→2024**, **validation 2024→2025-07**, **sealed 2025-07→2026-07** (+ ETH/SOL transfer).

---

## 1. Notation

- `t` — bar index (4h BTC primary; 1H/15m permitted for finer experts, all causal).
- `K` — number of experts. `R` — number of regimes (tradeable + FLAT).
- `r(t) ∈ {1..R}` — regime label at bar `t` (gating network output).
- `r_k(t) ∈ ℝ` — expert `k` raw signal at `t` (sign = direction, magnitude = conviction).
- `s_k(t) ∈ [-1,+1]` — normalized signed expert score.
- `W ∈ ℝ^{R×K}`, `W[r,k] ≥ 0` — regime-conditional weight matrix (the ONLY object fit to returns).
- `M(t) ∈ [-1,+1]` — master score.
- `τ` — conviction threshold; `q` — confluence-count guard.
- `p_eff` — effective parameter count = `#{(r,k) : W[r,k] > 0}` after sparsification.

---

## 2. Component A — Regime Classifier (the gating network)

### 2.1 Causality

Reuse `v3/regime.py`. Every feature is computed from candles **≤ close of bar `t`**; the decision applies to entry at `t+1`. No future bars ever touch the label. The classifier is *trailing* (ADX/ATR lag by nature) but has **no look-ahead** — which is what "non-lagging" means operationally here.

### 2.2 Near-zero learnable DoF by design

Regime boundaries are **structural**, never fit to returns. All thresholds (`adx_trend`, vol ratios) are **frozen from the train fold**. Learnable degrees of freedom live in exactly one place — the matrix `W` (§3) — so the overfitting surface is small and auditable.

### 2.3 Default partition (3 tradeable + 1 FLAT)

`R` is a hyperparameter **capped by the power budget** (§4.2). Default collapses v3's 3×4 `DirState × VolState` grid:

| Regime | Definition (all causal, 4h close) | Expert territory |
|---|---|---|
| **TREND** | `ADX ≥ adx_trend` AND `vol ∈ {QUIET, NORMAL, HIGH}` | breakout / pullback |
| **CHOP** | `RANGING` AND `vol ∈ {QUIET, NORMAL}` | mean-reversion |
| **STRESS** | large ATR expansion + directional gap (`vol = HIGH`-in-range / `EXTREME` transition) | free-OHLCV **proxy** for a cascade |
| **FLAT** | `EXTREME` / ambiguous → **weight row = 0, forced no-trade** | stand aside (preserves v3 extreme→flat invariant) |

Features: `ADX(adx_period)`, `EMA(fast) − EMA(slow)` sign (direction); `ATR(atr_period) / rolling-median-ATR` = `vol_ratio` (volatility). All already implemented in `v3/indicators.py` and `v3/regime.py`.

### 2.4 Free-data honesty flag

The regimes named in the original brief — **Liquidation Cascade** and **Passive Absorption** — are **NOT** derivable from free OHLCV+OI. They require liquidation/order-book/CVD feeds that are human-ops-gated (`deribit-chain-collector`, `bybit-trades`). The spec defines a `Regime` **protocol** so those swap in later without touching the combiner. Within free data, **STRESS is an explicit proxy**, labeled as such, not a claim to detect real cascades.

---

## 3. Component B — Expert normalization → weighting matrix → trigger

### 3.1 Expert protocol

An expert `e_k` emits a **causal** raw signal `r_k(t)` (sign = direction, magnitude = conviction, arbitrary scale). Existing closed lanes wrap to this protocol: capitulation-fade, session-sweep, vol-compression, breakout, pullback, reversion, MTF-confluence, etc. A flat/no-opinion expert emits `0`.

### 3.2 Normalization — summing heterogeneous strategies

Map every expert onto a common **signed unit scale** via **causal, distribution-free rank standardization** (fat-tail robust; consistent with the project's bootstrap-hardening bias):

```
s_k(t) = sign(r_k(t)) · F̂_k(|r_k(t)|)   ∈ [-1, +1]
```

where `F̂_k` is the empirical CDF of `|r_k|` on a **train-frozen or strictly-trailing** window. `s_k(t)` is a transform of the expert's **own signal history** — it uses **no returns and no future data** — which is precisely what makes summing experts legitimate. `0` = "no opinion."

**Alternate offered:** robust z-score → `tanh` squash: `z_k = (r_k − median_k)/(1.4826·MAD_k)`, `s_k = tanh(z_k)`, statistics from the train fold only. Rank is the default (distribution-free); robust-z is the alternate. Both are bounded, signed, unit-scaled, causal, train-frozen.

### 3.3 Master score

With `W ∈ ℝ^{R×K}`, `W[r,k] ≥ 0`, at regime `r = r(t)`:

```
          Σ_k W[r,k] · s_k(t)
M(t) = ─────────────────────────   ∈ [-1, +1]
          Σ_k W[r,k] + ε
```

**Row-sum normalization** makes the trigger threshold `τ` **regime-invariant** — a high-conviction bar means the same thing in TREND as in CHOP; without it, fatter-weighted regimes would trade more (a confound). The all-zero FLAT row forces `M = 0` → stand-aside. `ε` avoids div-zero.

### 3.4 Trigger

Enter at `t+1` open when **all** hold:

1. `r(t)` is tradeable (not FLAT), AND
2. `|M(t)| ≥ τ` (conviction threshold), AND
3. (optional confluence guard) `#{k : sign(s_k(t)) = sign(M(t)), W[r,k] > 0} ≥ q` — demands multiple uncorrelated experts agree.

Side `= sign(M(t))`.

**Sizing and exits stay the frozen v3/v2.2 bracket.** The combiner outputs **direction + conviction only**; exits never become another degree of freedom (v3 principle: "identical exits isolate entry selection"). `τ, q` are hyperparameters selected on **validation via deflated CI** (§4.5), counted as trials.

---

## 4. Component C — Overfitting defense (the deliverable)

Seven interlocking controls.

### 4.1 Learnable-DoF isolation

Exactly **one** object is fit to returns: `W`. Regime boundaries, expert normalization statistics, sizing, and exits are all frozen (theory or train-only descriptive stats). The overfitting surface is `W` alone.

### 4.2 Power budget as a *precondition* (the router lesson)

`p_eff = #{(r,k) : W[r,k] > 0}` after sparsification. Hard rule enforced **before** fitting:

```
p_eff ≤ N_train_trades / m ,   m ≥ 50 trades per effective weight (default; never < 30)
```

If desired `R×K` exceeds budget, the framework MUST **coarsen R**, **drop experts (K)**, or **refuse to run**. The n=36 router is the counterexample this rule exists to prevent — power becomes a precondition, not a post-mortem.

### 4.3 Constrained shrinkage estimator for `W` (Approach B)

Per regime `r`, on the **train fold only**:

1. **Conditional edge:** `ê_{r,k} =` mean forward-R when expert `k` fired in regime `r` (unweighted, fixed exit — isolates selection from sizing).
2. **Non-negativity + sign-lock:** `W[r,k] = max(0, ê_{r,k})` **only if** `sign(ê_{r,k})` matches expert `k`'s declared direction; else `0`. An expert is never learned "in reverse" — that is fitting noise.
3. **James-Stein shrinkage** toward the equal-weight prior `w̄_r`:
   ```
   W[r,·] ← (1 − λ_r)·W[r,·] + λ_r·w̄_r
   ```
   with `λ_r` increasing as within-regime sample `n_r` shrinks (form `λ_r = K / (K + (n_r − K − 2)·SNR)`, clipped to `[0,1]`). Thin `n_r` → weights collapse to equal-weight: **maximum humility where data is thin.**
4. **L1 sparsity:** threshold small weights to `0` (drives `p_eff` down). Sparsity strength selected on validation.

The estimator **cannot manufacture conviction from noise**: the prior is equal-weight, and the estimator is non-negative + sign-locked + shrunk. Where a regime has real conditional signal *and* enough samples, `W` tilts toward it; otherwise `W → equal-weight or 0`.

### 4.4 Nested walk-forward, sealed-once (reuse `evaluate.py`)

Frozen splits:

- **Train 2020→2024** — fit `W`, normalization stats, regime thresholds.
- **Validation 2024→2025-07** — pick `τ, q, λ`, L1 strength via **deflated CI** (not raw Sharpe).
- **Sealed 2025-07→2026-07 + ETH/SOL transfer** — spent **ONCE**, no re-fit.

Anchored/rolling multi-fold across train+val is used for `W` stability; the sealed window is strictly terminal.

### 4.5 Deflated significance + trial accounting

Every combiner configuration evaluated on validation is a **trial**. Feed `n_trials` into `foundation.metrics.deflated_sharpe`. **Gate on DSR**, not Sharpe. Block-bootstrap CI (block `T = 12`, matching v3) on combined equity: **ev/trade CI must exclude 0 AND clear the 0.05R econ bar by ≥2×** — the exact gate that stopped the `matrix-step-a-router` lockbox spend.

### 4.6 Null calibration = Gate-0 (the vol-compression lesson — non-negotiable)

**Before any live claim**, run the *entire frozen pipeline* on:

1. **iid-shuffled** expert signals (destroy time structure, keep marginals),
2. **sign-flipped / phase-randomized** experts,
3. the **known-dead expert set** (capitulation, session-sweeps, vol-compression, as closed).

The framework **MUST return NEGATIVE** (`W → ~equal-weight`, no gate passes, `DSR ≈ 0`). If it "finds edge" on **any** null, the combiner is a **tautology → HALT and fix the gate.** This is the operational definition of "a valid gate must fail on null," and it is **milestone-0** of any future implementation.

### 4.7 Pre-registered kill rule

The tuple `(regime-set × expert-set × combiner-config)` is **hash-frozen** before the sealed run. If sealed fails Gate1 / CI / DSR: the tuple is **retired**, the sealed window is **burned**, and there is **no re-fit on the same data** (a re-tune = a new registration on new data). Mirrors the v3/router discipline exactly.

---

## 5. Interfaces (protocol boundaries, for a later build)

The spec defines three protocols so components remain independently testable and swappable:

- **`Regime`** — `classify(candles≤t, cfg) → regime_label`. Swap the free-OHLCV proxy for a deriv/order-book classifier later without touching B or C.
- **`Expert`** — `signal(context≤t) → float` (raw, causal). Any closed lane wraps to this.
- **`Combiner`** — `fit(train) → W`; `score(s_vector, regime) → M`; carries `τ, q`. All learnable DoF live here.

The **evaluation harness** (`evaluate.py` extension) orchestrates: normalize → gate (regime) → weight (`W`) → trigger → Gate-0 null → power check → walk-forward → DSR/CI → sealed → kill rule.

---

## 6. Explicit non-goals (YAGNI)

- **No free-parameter regression fit** of `W` (Approach C rejected — the documented failure mode).
- **No learned regime boundaries** — structural only, to keep DoF isolated in `W`.
- **No new exit/sizing logic** — frozen v3 bracket, to isolate entry selection.
- **No exotic (cascade/absorption) regimes on free data** — protocol stub only until the deriv/order-book feeds clear human-ops gating.
- **No claim of edge.** The deliverable is the protocol; the expected verdict on current data is a *certified refusal*.

---

## 7. Expected outcome (pre-registered honesty)

Given the closed-lane record, the most probable results are, in order:

1. **Power budget refuses** the desired `R×K` on the current expert/trade counts → coarsen or halt.
2. **Gate-0 null calibration passes** (framework returns NEGATIVE on nulls) but the **live run also returns NEGATIVE** (no conditional edge to combine) → clean, publishable negative; sealed window preserved unspent.
3. **Least likely:** a genuinely uncorrelated conditional edge survives shrinkage + power + DSR + sealed → small-size candidate, *not* proven edge (BTC-1yr low power).

Outcome (2) is the framework working correctly. Outcome where a null "passes" is a **bug in the gate**, not a discovery.
