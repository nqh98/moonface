# BTC Drift Basket (beta-neutral residual drift) — GATE

## Verdict: CLOSED_NEGATIVE

- asof: 2026-06-28T11:36:56.067752+00:00  research_days: 1893  dsr: 0.016603
- holdout MAR: -0.8545  holdout DD: -0.47758
- stages: s1=False s2=False s3=False s4=True

## Diagnostics
- distinctness corr vs momentum: 0.11
- full portfolio beta: 0.0027  left-tail corr to BTC: 0.0023

(no diagnostic red flags)

Paper-only. A single frozen design (n_trials=1). closed_negative fires the kill rule: structural diversification does not defeat the drawdown wall.

## Cost-accounting note

Funding cost is charged unscaled by leverage in basket.simulate_basket (equity drag should be lev*fund, not fund), understating costs by up to MAX_LEVERAGE=5x. Biases optimistic. Turnover costs are lev-scaled. A closed_negative verdict is conservative-credible; a paper_candidate upset must be re-checked with lev-scaled funding.
