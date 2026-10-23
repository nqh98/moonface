# forced_error v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Design spec:
`docs/research-log/specs/2026-07-08-forced-error-harvesting-design.md`.

## 1. Hypotheses (two pre-committed trap setups, BTC/USDT:USDT 1h)

**Setup 1 — Failed Breakout Harvest (SHORT).** At bar t:
`high_t > donchian_upper_24(t-1)` (resistance pierced intrabar) AND
`z_o = zscore_180(log(OI_t / OI_{t-L})) >= +k` (crowd loaded) AND
`z_v = level_zscore_180(log(volume_t)) >= +k` (volume participation, UNSIGNED
proxy — not CVD; a **level** z-score, NOT the log-change z-score, because
log-volume is positive-definite) AND `close_t < donchian_upper_24(t-1)` (closes
back inside the range = failure) -> SHORT.

**Setup 2 — Failed Fade Squeeze (LONG).** At bar t:
`z_r = zscore_180(log(P_t / P_{t-L})) >= +k` (rallied) AND
[`funding_t <= 20th-percentile(funding, trailing 720)` **AND** `funding_t < 0`]
(crowd shorting the top — deeply NEGATIVE, both relative-low AND actually
negative) AND `z_o >= +k` (OI climbing) AND (`low_t < low_{t-1}` AND
`close_t > close_{t-1}`) (downward probe absorbed) -> LONG.

Exit `fixed_bracket{atr_period:14, k_stop:2.0, m_tp:1.0}`, fraction 0.01.

> **Construction note (frozen at build time).** The funding gate requires BOTH a
> bottom-percentile reading AND an actually-negative rate; a pure percentile gate
> was rejected because it fires in all-positive-funding regimes, contradicting the
> "deeply negative" mechanism. The volume term uses a level z-score of log(volume)
> (returns None on zero dispersion) rather than the log-change z-score, which
> degenerates to +inf on positive-definite series and would make the gate inert.
> Both corrections were made before any OOS evaluation.

## 2. Treatment vs control (the one variable per setup)

- Setup 1 control = `failed_breakout_naive` (SHORT on the pierce + close-back-
  inside failure, OI and volume gates removed). The Setup-1 OI-only ablation
  (`use_volume=false`) is a reference baseline, NOT a counted trial.
- Setup 2 control = `funding_fade_long` (LONG on the same deeply-negative funding
  trigger alone — the already-CLOSED-NEGATIVE funding fade). This tests whether
  event-conditioning on OI-climb + absorption rescues a dead standalone signal.

Controls inherit the treatment's exit and fraction. Grid per setup:
`L in {3,6} x k in {1.5,2.0}` = 4 treatment cells (donchian_n=24, W=180,
funding_pct=0.2, funding_window=720 all fixed). Total treatment trials = 8.

## 3. Evaluation

Ladder: screen (>=30 trades AND expectancy_R>0) -> holdout (MAR>0, DD>=-0.30,
strict dominance vs control on BOTH MAR and Sharpe) -> DSR >= 0.95
(n_trials=8, pooled across both setups) -> cross-coupling surrogate-null gate
(real holdout MAR in the OI block-shuffle surrogate upper tail, p<0.05, funding
held fixed) -> one-touch lockbox tail (MAR>=1.0, DD>=-0.30, >=20 trades,
dominance). Plus rolling walk-forward with aggregate MAR/Sharpe dominance.

The surrogate-null gate is validated by a build-time assertion that it REJECTS a
null-OI bundle in which the signal genuinely fires (>=10 holdout trades) yet OI
is independent of forward returns — `tests/test_forced_error_null_calibration.py`.
This is the vol_compression lesson: a valid gate must be able to fail.

## 4. Decision

-> PAPER-WATCH (paper only) iff >=1 treatment cell clears stages 1,2,3.5, DSR,
the surrogate-null gate, AND stage 4, AND strictly dominates its control.
-> CLOSED NEGATIVE otherwise. **Kill rule:** no v2, no grid expansion, no
direction flip, no added family, no multi-asset, no swapping the volume proxy
for signed CVD without a NEW pre-registration.

## 5. Setup 3 (Liquidation Absorption) — DEFERRED

Setup 3 is not testable on free historical data (no liquidation archive; live
feed throttled 1/s/symbol). Its data collector ships this cycle (Track B) but its
pre-registration is DEFERRED behind a readiness gate (>=6 months accrual AND >=
target cascade-cluster count) documented in
`experiments/newdata/FREE_DATA_FEASIBILITY_liquidations.md`.
