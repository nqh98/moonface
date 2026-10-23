# macro_regime — Results & Verdict

**Lane:** macro-liquidity regime instrument (unsupervised GMM over exogenous DXY / US10Y / Gold).
**Status:** **CLOSED — FRAGILE/DEAD (2026-07-08).** No sealed/lockbox data spent. In-sample only.

## What was built

- `macro_regime_model.py` — quarantined, zero-leakage GMM regime instrument (single-split
  primitive + expanding walk-forward, exogenous-only features, deterministic label
  canonicalization, entropy output, CLI). 20 tests.
- `regime_diagnostic.py` — in-sample descriptive go/no-go probe (regime × BTC forward outcome
  table, entropy split) **+ era-stability sub-probe**. 10 tests. **No gate, no edge claim.**

## Step-1 descriptive probe (full sample 2016→2025, 2113 walk-forward labels)

Two candidate patterns appeared in the pooled sample:
- **"State-1-flat":** at h=20, State 1 (~33% of days) showed near-zero forward return (+0.09%)
  vs States 0/2 (+3.4% / +2.0%); return spread 3.3%.
- **Entropy-monotone:** confident (low-entropy) days preceded higher BTC returns than uncertain
  days at every horizon (h=20: +3.31% vs +0.19%).

Magnitudes were already small vs BTC vol (h=1 spread ~12 bps against ~3.6% daily vol → IR ≈ 0.03),
and the 2113 samples are heavily overlapping/autocorrelated — so this was flagged *marginal*, and
gated behind a free era-stability check before any pre-registration.

## Step-2 era-stability probe (pre-committed kill: pattern must hold in EVERY era) — h=20

| Era | n | State 1 fwd20 | flattest state | state1_is_flattest | return_spread | entropy_monotone | pattern_holds |
|---|---|---|---|---|---|---|---|
| ..2020 (≈2018–2019) | 479 | **+0.051** | 0 | **False** | 0.151 | True | **False** |
| 2020..2023 | 756 | −0.047 | 1 | True | 0.163 | True | True |
| 2023.. (2023–2025) | 878 | +0.018 | 0 | **False** | **0.015** | True | **False** |

**Read:**
- The **"State-1-flat" pattern is entirely a 2020–2022 artifact.** It **rank-flips** across eras:
  in 2018–2019 State 1 was the *best* regime (+5.1%); in 2023–2025 the regimes barely separate
  returns at all (spread collapses to 1.5%) and State 0 is flattest. The pooled 3.3% spread was
  one era leaking into the average.
- **Entropy-monotonicity does survive all three eras** — but (a) it is not a standalone tradeable
  filter without the (fragile) regime-return structure, (b) its 2023–2025 magnitude is weak, and
  (c) "confident macro regime ⇒ BTC up" is almost certainly **crypto beta / risk-on**, the same
  confound that closed the breadth family. It does not rescue the hypothesis.

## Verdict

Per the pre-committed rule (*pattern flips / degrades / disappears in any era ⇒ FRAGILE*), the
**macro-exogenous regime-filter hypothesis is FRAGILE/DEAD.** Lane closed. **No sealed data spent.**
Consistent with the program's prior macro-conditioning closures (`exogenous`, `regime_overlay`,
`regime_selector`, `macro_event`, `donchian_volregime`).

The instrument + diagnostic remain as **reusable tooling** (committed) for any future *new-data*
regime question, but the free macro-exogenous axis is finished — no reopening under a new framing.
