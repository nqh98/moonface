# orderflow_microstructure v1 — Pre-Registration

Frozen **before any out-of-sample evaluation**. A changed design requires a new
experiment directory. Lineage: the MoonFace 4h directional / funding /
positioning program line has closed negative at 4h–daily (e.g.
`funding_fade_voltarget`, closed negative 2026-07-02); the single new lever is
the **intraday horizon** (15m bars + 5m-native order-flow microstructure) with
a reversal-favoring exit and intraday-tuned gates. Design spec:
`docs/research-log/specs/2026-07-02-orderflow-microstructure-design.md`.

## 1. Hypothesis
On BTC/USDT:USDT 15m perps, `oi_flush_reversal` / `taker_flow_momentum` /
`liquidity_sweep_reclaim` + `fixed_bracket{k_stop:2.0,m_tp:1.0,atr_period:14}`
earn positive OOS risk-adjusted return AND strictly beat a `donchian_break`
control on MAR and Sharpe — i.e. the edge that is arbitraged away at 4h
survives at intraday.

## 2. Treatment vs control (the one variable)
- Control: `donchian_break{n:48|96,long_only:False}` (classic trend breakout).
- Treatment: the order-flow family spec, paired by horizon (window/swing_n=48
  ↔ n:48; =96 ↔ n:96). Same 15m timeframe, same `fixed_bracket` exit, same
  `0.01` fraction, same cost — only the **entry signal** differs. Treatment
  grid = 10 specs (oi_flush_reversal ×4, taker_flow_momentum ×4,
  liquidity_sweep_reclaim ×2); controls are reference baselines, not trials.

## 3. Evaluation (hybrid)
Ladder (screen 70% with **≥100-trade** floor + expectancy_R>0; holdout MAR>0
& DD≥−0.30 + dominance; DSR ≥ 0.95 with **n_trials=10**; one-touch lockbox tail
MAR ≥ 1.0 / DD ≥ −0.30 / **≥20 trades** + dominance) + rolling walk-forward
(6mo train-offset / 2mo test / 2mo step at 15m, dominance on aggregate MAR &
Sharpe). Intraday floors pass through the stage functions' keyword overrides /
local constants; the frozen `ladder` constants are **not** mutated. A
treatment spec is eligible only if it dominates its paired control at holdout,
WF aggregate, and lockbox tail.

## 4. Decision
- → PAPER-LIVE WATCHING iff ≥1 treatment spec clears stages 1, 2, 3.5, DSR,
  and 4 AND strictly dominates its `donchian_break` control. The promoting
  family alone goes to watch.
- → CLOSED NEGATIVE otherwise. Kill rule: no v2, no added family, no
  gate/exit relaxation. n_trials = 10.

## 5. Run
`python tools/research.py orderflow`
