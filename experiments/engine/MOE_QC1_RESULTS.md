# Regime-MoE Combiner — Results: q_confluence=1 variant (Trial 2)

**Run:** 2026-07-09 · **config hash:** `685a8af8…` (matches registration ✅) ·
result: `experiments/engine/moe_eval_qc1.json`
**Registration:** `MOE_QC1_REGISTRATION.md` (committed `7a3ca1a`, before this run).

## Verdict: `CLOSED_NEGATIVE_VALIDATION` — tested-and-failed (not a no-fire)

The `q_confluence=1` fix worked structurally: the combiner **fired 353 validation trades**
(trial 1 fired 0). It was genuinely tested and rejected at Gate-1.

### Gate-0 null calibration: PASSED, and exercised hard
Unlike trial 1 (nulls barely traded), q=1 lets the nulls fire heavily — yet all stay
non-positive:

| null | n trades | p_eff | validation CI positive |
|---|---|---|---|
| iid_shuffle | 455 | 3 | **False** |
| phase_randomize | 279 | 5 | **False** |
| sign_flip | 1525 | 3 | **False** |

`passed_negative=True`. Strong evidence the pipeline does not manufacture edge from noise
even when the confluence gate is wide open.

### Power: PASSED
n_train=9983, allowed p_eff=199, actual p_eff=3. Fitted `W` unchanged from trial 1
(q_confluence affects only the live decision gate, not the weight fit):
`TREND→BREAKOUT 0.19, STRESS→REVERSION 0.45, CHOP→REVERSION 0.02`.

### Gate-1: FAILED (the real result)
| metric | MoE | v2.2 base |
|---|---|---|
| n validation trades | 353 | — |
| net_r | **+0.34** (≈0.001 R/trade — flat) | — |
| block-CI on mean-R | **[-0.4356, +0.455]** → straddles 0 | — |
| max_dd_r | **-62.52** | -11.65 |
| net_r_3x | **-110.10** | — |

Essentially zero net edge, CI straddling zero, and ~5× worse drawdown than the base.
Gate-1 correctly rejects.

### Sealed window: NOT opened (gate2/gate3 = null)
Halted at Gate-1 → **sealed 2025-07→2026-07 remains UNSPENT** for the MoE family.

## Line status
Per the registration kill rule, this was the last cheap config lever on the current
3-mechanism (BREAKOUT/PULLBACK/REVERSION) expert set. Trial 1 (q=2) = no-fire;
trial 2 (q=1) = fires but flat with worse DD. **The config-tuning line is closed.**
Any further attempt requires a *new registration* with either new experts
(capitulation-fade / session-sweep / vol-compression wrappers the framework already
supports) or new data — not another threshold tweak. Trials used: 2 of ≤12.
