# price_oi_divergence v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Design spec:
`docs/research-log/specs/2026-07-08-price-oi-divergence-design.md`.

## 1. Hypothesis
On BTC/USDT:USDT 1h perps, a price extension high while open interest
contracts is an unbacked breakout (short-covering / long profit-taking, not
fresh commitment) that mean-reverts. Signal:
`z_r = zscore_180(log(P_t/P_{t-L}))`, `z_o = zscore_180(log(OI_t/OI_{t-L}))`;
ENTER SHORT when `z_r >= +k AND z_o <= -k`. Direction is pre-committed SHORT.
Exit `fixed_bracket{k_stop:2.0,m_tp:1.0,atr_period:14}`, fraction 0.01.

## 2. Treatment vs control (the one variable)
Control = `price_extension_short` (SHORT when `z_r >= +k`, OI gate removed),
same W/L/k/exit/fraction/asset. The OI gate is the only difference. Grid = 4
treatment cells: L in {3,6} x k in {1.5,2.0}, W=180. Controls are reference
baselines, not trials.

## 3. Evaluation
Ladder: screen (>=30 trades + expectancy_R>0) -> holdout (MAR>0, DD>=-0.30,
dominance vs price-only control) -> DSR >= 0.95 (n_trials=4) ->
cross-coupling surrogate-null gate (real holdout MAR in the block-shuffle
surrogate upper tail, p<0.05) -> one-touch lockbox tail (MAR>=1.0, DD>=-0.30,
>=20 trades + dominance). Plus rolling walk-forward (`orderflow_wf`) with
aggregate MAR/Sharpe dominance.

## 4. Decision
-> PAPER-WATCH iff >=1 treatment cell clears stages 1,2,3.5, DSR, the
surrogate-null gate, and stage 4 AND strictly dominates its control. Paper
only.
-> CLOSED NEGATIVE otherwise. Kill rule: no v2, no added family, no direction
flip, no CVD bolt-on, no grid expansion without a new pre-registration.
