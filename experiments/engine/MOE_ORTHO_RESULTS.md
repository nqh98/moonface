# Regime-MoE — Results: Orthogonal-Expert Trial 3 (FUNDING+OI)

**Run:** 2026-07-10 · **identity_hash:** `c4840e61eba4738d21d4aab52385c5b3a88ea5aadd332ce02f6249bd91185e76`
(matches registration ✅) · result: `experiments/engine/moe_eval_ortho.json`
**Registration:** `MOE_ORTHO_REGISTRATION.md` (committed `8400b2c`, before this run).

## Verdict: `CLOSED_NEGATIVE_VALIDATION` — tested-and-failed (not a no-fire)

The combiner fired 364 validation trades and was genuinely tested at Gate-1, then rejected.

### Gate-0 null calibration: PASSED, exercised hard
| null | n trades | p_eff | dsr | validation CI positive |
|---|---|---|---|---|
| iid_shuffle | 1339 | 5 | 0.0 | **False** |
| phase_randomize | 1192 | 6 | 0.0 | **False** |
| sign_flip | 1194 | 4 | 0.0 | **False** |

`passed_negative=True`. All three nulls traded heavily (n≈1200-1340) and stayed clean —
the RNG-isolation fix (see build notes) is holding up under a real, full-scale run.

### Power: PASSED
n_train=59841, allowed p_eff=1196, actual p_eff=5. Fitted `W`:

| regime | expert | weight |
|---|---|---|
| TREND | BREAKOUT | 0.1905 |
| TREND | OI | 0.1515 |
| CHOP | REVERSION | 0.0234 |
| STRESS | REVERSION | 0.496 |
| STRESS | OI | 1.0914 |

**FUNDING got zero weight in every regime** — the crowd-fade signal was never selected.
**OI was selected in TREND and STRESS**, with a large weight in STRESS (1.09) — the one
orthogonal signal the fitter actually picked up.

### Gate-1: FAILED (the real result)
| metric | MoE | v2.2 base |
|---|---|---|
| n validation trades | 364 | — |
| net_r | +18.04 | — |
| block-CI on mean-R | **[-0.3141, +0.4737]** → straddles 0 | — |
| max_dd_r | **-51.91** | -11.65 (~4.5× worse) |
| net_r_3x | **-94.33** | — |

Net_r is nominally positive this time (unlike trial 2's near-zero), but the CI still
straddles zero — not statistically distinguishable from noise — while drawdown is ~4.5×
the base and cost-stressed net_r is deeply negative. Gate-1 correctly rejects.

### Sealed window: NOT opened (gate2/gate3 = null)
Halted at Gate-1 → **sealed 2025-07→2026-07 remains UNSPENT**, now across all 3 MoE trials.

## Interpretation
Adding FUNDING+OI experts changed which regime/expert combinations get weight (OI displaced
some price-expert weight in TREND/STRESS) but did not change the outcome: the combiner still
fails to clear a CI-significant, drawdown-acceptable edge in validation. Consistent with the
honest prior (OI standalone dead, funding-fade transfer dead) — regime-conditioned combination
does not rescue either signal.

## Line status
Trial 3 of ≤12 (`EFFECTIVE_TRIALS`). Free-data orthogonal-expert line (funding+OI on the
current mechanism set) is now **CLOSED NEGATIVE**. Any further MoE attempt needs either new
non-price data (the program's remaining free-data levers are largely exhausted per
[[funding-fade-transfer-results]], [[oibuild-mechanism-verdict]]) or a materially different
combination architecture — not another expert/threshold tweak on this base.
