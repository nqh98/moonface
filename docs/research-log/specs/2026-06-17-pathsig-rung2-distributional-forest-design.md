# Path Signal — Rung 2: Distributional Random Forest (design)

- **Date:** 2026-06-17
- **Status:** Design approved; implementation plan pending.
- **Program:** `docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md`
- **Pre-registration:** `experiments/path_signal/PREREGISTRATION.md` (frozen 2026-06-16)
- **Rungs below:** rung-0 `src/moonface/research/pathsig/baseline.py`
  (`experiments/path_signal/rung0_baseline.json`), rung-1
  `src/moonface/research/pathsig/ensemble.py`
  (`experiments/path_signal/rung1_ensemble.json`).

## 1. Position in the ladder

Rung 2 is **the hypothesis** (design §3.1, "A"): a learned model that ingests the
frozen point-in-time feature vector at each 4h bar and outputs a *predictive
distribution of the forward path*, with the trade driven by the **asymmetry** of
that distribution rather than a point estimate. It must (a) **beat rung-1 and
rung-0 on identical folds** and (b) **clear the deflated-Sharpe gate**. The
two-part test is what makes any edge attributable to path-modeling rather than to
ensembling, regime, or model capacity.

Kill rule (from the pre-registration, restated): rung 2 fails to beat rung 1 OR
fails the gate ⇒ "the framework was the limiting factor" is **falsified on
existing data**; escalate to a separate new-data program. **No parameter rescue.**

## 2. Deviation from the program spec (logged)

Program design §2 names the model class "gradient-boosted quantile/probabilistic
heads." This environment has **only numpy** (no lightgbm / xgboost / sklearn) and
the whole `pathsig` package is pure-stdlib. Rung 2 therefore uses a **from-scratch
distributional random forest (DRF)** instead of gradient boosting:

- It is **tree-based**, which the program spec's rung-3 promotion gate already
  assumes ("A's tree-based version clears the gate").
- It is **genuinely distributional**: each leaf carries the empirical path-label
  set, so `P(up)`, `E[MAE]`, `E[MFE]`, and return quantiles fall out directly —
  the literal "quantile/probabilistic head."
- Bagging is **less overfit-prone** than boosting on ~1700 noisy bars, which
  serves the program's overriding anti-overfit discipline.
- It adds **no dependency**, preserving the package's pure-stdlib + numpy style.

No feature is added or changed. The frozen `FEATURE_NAMES` list and the sealed
lockbox boundary are untouched (the pre-registration forbids feature changes
without a version bump and a fresh lockbox).

## 3. The model — `forest.py` (pure numpy)

### 3.1 Input
The frozen 16-dim `FEATURE_NAMES` vector (`features.py`) at **every**
label-complete `Sample` bar — not only signal-fire bars. This is the
architectural shift from rungs 0/1: the model conditions on *state*, so it emits a
distribution on every bar; trade frequency is controlled downstream by the
decision threshold.

### 3.2 Tree
A CART regression tree grown to **minimize the variance of `ret_r`** (direction is
the quantity whose sign and asymmetry are traded). Stopping: `max_depth` reached,
or a node has fewer than `2 * min_leaf` samples, or no split improves variance.
Each **leaf stores the full member set** of `(ret_r, mae_r, mfe_r)` labels, not a
summary — the leaf *is* a conditional path distribution.

### 3.3 Forest
`n_trees` bagged trees. Each tree fits a bootstrap resample of the train rows; at
each split a random subset of `mtry` features is considered. Prediction at a
feature vector `x`: route `x` to one leaf per tree and **pool all leaf member
labels across the forest** into one empirical conditional distribution:

- `p_up`      = fraction of pooled `ret_r > 0`
- `exp_ret_r` = mean pooled `ret_r`
- `exp_mae_r` = mean pooled `mae_r`  (≤ 0)
- `exp_mfe_r` = mean pooled `mfe_r`  (≥ 0)
- `q05, q50, q95` = quantiles of pooled `ret_r` (carried for the ruin clamp)

The first four fill the existing `policy.Distribution` unchanged. Quantiles are
returned alongside (a small `PathPrediction` carrier) and are **not** part of
`Distribution`, so `decide()` stays byte-identical to rungs 0/1.

### 3.4 Determinism
All randomness (bootstrap, feature subsample) is drawn from a single
`numpy.default_rng(seed)` with a **frozen seed**. Runs are reproducible and the
one-touch lockbox stays one-touch.

## 4. Decision — unchanged policy, for attribution

Reuse `policy.decide(dist, edge_threshold, kelly_scale, max_fraction)` verbatim:
`edge = exp_ret_r / |exp_mae_r|`, WAIT default, conviction sizing, hard
`max_fraction` cap. **The only thing different from rungs 0/1 is the source of the
`Distribution`.** Any improvement is therefore attributable to the model.

**Ruin clamp** (program design §6.3, "hard-capped by the ruin constraint"): after
`decide()`, if the directional 5th-percentile return (`q05` for LONG, `-q95` for
SHORT) is worse than a frozen `ruin_q05_r` threshold, the size is zeroed. This is
a wrapper around `decide()`; its core is untouched. `kelly_scale`, `max_fraction`,
`taker_bps`, `slippage_bps` reuse the rung-0 constants for cross-rung comparability.

## 5. Nested validation — the anti-overfit spine

- **Outer folds:** the same `walkforward.walk_forward_folds(n_samples, n_folds,
  embargo=h, lockbox_fraction=0.2)` used by rungs 0/1 — anchored, purged +
  embargoed by the horizon, lockbox tail excluded. **Identical folds** to rungs
  0/1, enabling the head-to-head.
- **Inner selection:** inside each outer **train** block, an inner
  purged/embargoed split selects the hyperparameter config. The inner split never
  touches the outer test indices. Selection objective: best inner risk-adjusted
  Sharpe (ties → fewer trades, i.e. higher threshold).
- **Frozen hyperparameter grid:**
  `max_depth ∈ {3, 5}` × `min_leaf ∈ {30, 60}` × `mtry ∈ {4, 8}` = **8 structure
  configs**; `n_trees = 200` (fixed); `edge_threshold ∈ {0.10, 0.20, 0.30}`. The
  inner fold selects jointly over **structure × threshold = 24 combinations**
  (program design §6.2 — threshold calibrated on the inner fold).
- **Deflation:** `n_trials` passed to `deflated_sharpe` = `|structure| ×
  |edge_thresholds| × len(horizons)` (= 8 × 3 × 2 = 48), the conservative reading
  of the pre-registration ("every hyperparameter combination × every rung
  evaluated") — `edge_threshold` is counted as a hyperparameter. `trial_srs` = the
  inner-CV Sharpes of every evaluated combination. This is the single most
  important anti-overfit rule for the learned model.

## 6. Lockbox — kept one-touch

The OOS outer folds produce the **decision gate** (DSR + dual-frame metrics). The
sealed final ~20% tail is opened **only** by a separate, explicitly-invoked step
(`rung2 --open-lockbox`, a distinct function), run exactly once **after** OOS
success — never auto-folded into the standard run. This mirrors rungs 0/1, which
never touch the tail. The lockbox step refits on all usable (non-lockbox) data
with the OOS-selected config and scores the sealed tail once.

## 7. Verdict & output

Reuse `evaluate.evaluate_strategy` (dual frame: risk-adjusted MAR/Sharpe/DSR +
fixed −15R cap) and `costs.apply_costs`. Per horizon `h ∈ {6, 12}` the
concatenated outer-OOS decision stream yields one result with a verdict:

- `beats_rung0` — fixed-cap `total_r` exceeds the rung-0 floor AND risk-adjusted
  is not worse.
- `beats_rung1` — same comparison against the rung-1 result at the same horizon.
- `clears_gate` — DSR ≥ 0.95.
- **Success** (program design §5) = `beats_rung1 AND beats_rung0 AND
  clears_gate`, reported under both risk frames; lockbox tail must then ratify.

Artifacts: `experiments/path_signal/rung2_forest.json` (machine doc, mirroring
`rung0_baseline.json` / `rung1_ensemble.json`) and a `rung2_forest.md` run
document recording the verdict, mirroring the rung-0/1 run docs.

## 8. Files

| File | Role |
|---|---|
| `src/moonface/research/pathsig/forest.py` | DRF: tree growth, bagging, predict → `Distribution` + quantiles (the bulk). Pure numpy. |
| `src/moonface/research/pathsig/rung2.py` | Nested-CV harness, inner hyperparameter selection, outer-OOS replay, ruin clamp, verdict vs rung-0 floor + rung-1, doc builder, lockbox step. Mirrors `ensemble.py`. |
| `tools/path_signal.py` | Add `rung2` subcommand (mirrors `ensemble`), reads rung0 + rung1 docs for the head-to-head; `--open-lockbox` flag. |
| `tests/test_pathsig_forest.py` | Tree/forest unit behaviour: determinism, leaf distribution correctness, variance reduction, monotone-toy-signal recovery, mtry/bootstrap effects. |
| `tests/test_pathsig_rung2.py` | Nested CV has no leakage (inner never sees outer test), verdict logic, doc shape, no-trades path. |
| `tests/test_pathsig_rung2_cli.py` | CLI wiring with injected readers (offline). |

The frozen `FEATURE_NAMES` and the lockbox boundary are **not** modified.

## 9. Defaults chosen (recorded)

- Decide on **every** bar (the model conditions on state).
- Split criterion = **`ret_r` variance reduction**.
- Grid = **8 structure configs** + inner-calibrated `edge_threshold`; `n_trees=200`.
- Ruin clamp via directional **q05**.
- Lockbox as a **separate, explicitly-gated** step.

## 10. Out of scope

- Gradient boosting / new ML dependencies (see §2; deferred unless DRF is
  inconclusive for capacity reasons, which would be a rung-2 note, not a rescue).
- Rung 3 (sequence model "C") — gated behind rung 2 clearing the gate with
  capacity-limited residual signal (program design §3.2, §8).
- Any feature-list change (pre-registration: requires version bump + fresh
  lockbox).
- Parameter rescue after a kill (pre-registration kill rule).
