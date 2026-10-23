# funding_fade_voltarget v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Lineage: successor to `funding_fade_transfer` (closed
negative 2026-06-15) and the profit-maximization program; the single new lever
is per-trade vol/risk targeting. Design spec:
`docs/research-log/specs/2026-07-02-funding-fade-voltarget-design.md`.

## 1. Hypothesis
`funding_fade{window:60,z_thr:1.5}` + `fixed_bracket{k_stop:2.0,m_tp:4.0,atr_period:14}`,
sized by vol/risk targeting (constant stop-risk, iso-average-risk), earns
positive OOS risk-adjusted return on ETH and SOL AND beats the fixed-fractional
baseline on both MAR and Sharpe.

## 2. Treatment vs control (the one variable)
- Control: fixed-fractional `f = 0.01`.
- Treatment: `f_i = clamp(target_risk / atr_frac_i, 0, 5.0 * atr_frac_i)`, with
  `target_risk` calibrated so `mean(f_i over screen) = 0.01`. Same entries,
  exits, and splits — only the sizing rule differs.

## 3. Evaluation (hybrid)
Standard ladder (screen 70% / holdout, DSR ≥ 0.95, one-touch lockbox tail MAR
≥ 1.0 / DD ≥ −0.30 / ≥ 10 trades) + rolling walk-forward (3 yr train / 6 mo
test / 6 mo step, per-fold calibration). The treatment must clear every stage
AND strictly dominate the control on MAR & Sharpe at holdout, WF aggregate,
and lockbox tail.

## 4. Decision
- → PAPER-LIVE WATCHING iff BOTH ETH and SOL clear all stages and dominate.
- → CLOSED NEGATIVE otherwise. Kill rule: no v2, no fraction grid, no budget
  relaxation. n_trials = 2.

## 5. Run
`python tools/research.py voltarget`
