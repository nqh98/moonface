# price_oi_divergence v1 — Design

**Date:** 2026-07-08
**Status:** Approved (design)
**Lane:** `experiments/price_oi_divergence/` (new)
**Lineage:** Pivot away from pure price-action/OHLCV (fully priced-in or too noisy)
to BTC derivatives microstructure. Distinct from all prior OI work
(`positioning`, `liqladder`, `oibuild_study`, `orderflow_microstructure`,
`drift_screen_multifamily`) which tested OI/taker-flow as **standalone directional
drifts** — every one closed `mechanism_does_not_exist` / CLOSED NEGATIVE. This lane
tests the **price↔OI interaction (divergence)**, a two-variable conditional signal
the program has never systematically evaluated.

## 0. Scope decisions (frozen)

- **Flow substrate: OI only.** True tick-CVD requires reopening the sealed/dead
  aggTrades lane; the 5-min taker-ratio proxy already died standalone. v1 builds on
  `sum_open_interest` alone (clean, unspent in this construction). Concept 2
  ("Passive Absorption / CVD dumps") is **out of scope for v1** and may not be
  bolted on without a fresh pre-registration.
- **Estimator: B (standardized z-gap).** Regression-residual (C) is parked as a
  v1.1 refinement, only if B shows life. Rolling-correlation decoupling (A) is a
  diagnostic, never a tradeable spec.
- **Direction: SHORT only, pre-committed.** No long side, no both-directions search.

## 1. Hypothesis & mechanism

On BTC/USDT:USDT perps, when price pushes to a local **extension high while OI
contracts**, the move is driven by short-covering / long profit-taking rather than
fresh capital commitment — an *unbacked* breakout that mean-reverts. The mechanism
is falsifiable: if the effect is symmetric or long-favoring, the lane closes.

## 2. Signal (frozen math)

At each bar close, over normalization window **W**, with lookback **L** and
threshold **k**:

```
r_t  = log(P_t / P_{t−L})                    # price move over lookback L
o_t  = log(OI_t / OI_{t−L})                  # OI move over same lookback L
z_r  = (r_t − mean_W r) / std_W r            # self-normalizing, unit-free
z_o  = (o_t − mean_W o) / std_W o
ENTER SHORT  when  z_r ≥ +k  AND  z_o ≤ −k
D_t  = z_r − z_o                             # continuous intensity (diagnostics/ranking)
```

Healthy-trend baseline is `z_r ≈ z_o` (price up on new commitment). The signal
fires only on disagreement: price extended up (`z_r ≥ +k`) while OI contracts
(`z_o ≤ −k`).

**Exit:** existing frozen `fixed_bracket{k_stop, m_tp, atr_period:14}`. Only the
**entry** differs from the control — the exit, sizing, timeframe, and cost are held
identical.

**Pre-registered grid (frozen before any OOS look):**
- `L ∈ {3, 6}` bars
- `k ∈ {1.5, 2.0}`
- `W = 180` bars (matches the OI-family convention in `research/domains.py`)

→ **4 treatment cells.** `n_trials = 4` for DSR.

## 3. Control — the ablation (headline)

The "one variable" under test is the **OI gate**. Primary control removes exactly
that:

```
CONTROL (price-extension-only):  ENTER SHORT when z_r ≥ +k
```

Identical timeframe, exit, sizing, and cost — the OI condition is the *only*
difference. A treatment cell is eligible only if it **strictly dominates** its
paired price-only control on **MAR and Sharpe** at holdout, WF aggregate, and
lockbox tail. This proves OI carries information beyond "price ran up."

`donchian_break{n paired to horizon}` is retained as a **secondary sanity
baseline** only (not the eligibility gate).

## 4. Timeframe

- **1h primary.** OI is 5-min native → clean resample; intraday is the program's
  standing live lever.
- **4h deferred:** run only if a 1h cell shows life. Never run simultaneously with
  1h — protects the multiple-comparisons budget.

## 5. Data & cleaning (OI-specific)

- **Feed:** `sum_open_interest`, Binance Vision 5-min, BTC/USDT:USDT, 2020-09→.
- **Lookahead guard:** OI sampled as the last 5-min value with timestamp **≤ bar
  close**, aligned to the bar it informs. No future OI leaks into `z_o`.
- **Ramp drop:** discard the sparse 2020-09 startup period.
- **Log-domain hygiene:** require `OI > 0` for the log; forward-fill gaps capped at
  **1 bar**, else **mask** the bar (no synthetic divergence manufactured across data
  holes).
- **Units:** `sum_open_interest` is base-asset (BTC). Log-*change* is unit-invariant,
  so no USD conversion is needed. Assert no step-discontinuities (contract/unit
  resets) survive into the change series.

## 6. Evaluation ladder + the make-or-break null

Standard ladder (intraday floors via the existing stage-function keyword overrides;
frozen `ladder` constants are not mutated):

1. **Screen:** trade-floor + `expectancy_R > 0`.
2. **Holdout:** `MAR > 0`, `DD ≥ −0.30`, **dominance vs price-only control**.
3. **DSR:** `≥ 0.95` with `n_trials = 4`.
4. **One-touch lockbox tail:** `MAR ≥ 1.0`, `DD ≥ −0.30`, **≥ 20 trades**
   (the `min_n = 20` guardrail), + dominance.

Plus a **rolling walk-forward** cross-check (6mo train-offset / 2mo test / 2mo step
at the primary timeframe), dominance on aggregate MAR & Sharpe.

### Added hard gate — cross-coupling surrogate null

Beyond plain iid, run the **frozen pipeline** on a surrogate that **block-shuffles
OI relative to price**: each series keeps its own autocorrelation and marginal
distribution, but the price↔OI dependence is destroyed.

- **Pass condition:** the real edge clears the gate **AND the surrogate fails it.**
- **Kill condition:** if the surrogate reproduces the edge, the signal is a
  z-normalization / selection-bias artifact → **lane closes.**

This encodes the `vol_compression` post-mortem lesson (a valid gate must FAIL on a
properly-constructed null) directly as a gate.

## 7. Decision / kill rule

- → **PAPER-WATCH** iff ≥ 1 treatment cell clears the full ladder, dominates its
  price-only control at holdout + lockbox, **and** passes the surrogate-null gate.
  Only the surviving cell(s) go to watch. Paper only — no live capital.
- → **CLOSED NEGATIVE** otherwise. Kill rule: no v2, no added family, no direction
  flip, no CVD bolt-on, and no grid expansion without a **new** pre-registration in
  a new experiment directory.
