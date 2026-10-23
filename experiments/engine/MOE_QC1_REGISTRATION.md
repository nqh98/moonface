# Regime-MoE Combiner — Registration: q_confluence=1 variant (Trial 2)

**Registered:** 2026-07-09 (BEFORE any evaluation of this config — pre-registration).
**Frozen config hash (`moe_hash`):** `685a8af85b84377eacc7fd455691e367b3b57a9c5b00f9020f1ea07b837a9a3c`
**Config:** `MoeConfig(q_confluence=1)`; all other fields at defaults
(`tau=0.35, m_per_weight=50, shrink_snr=1.0, l1_frac=0.10, norm_mode="rank", seed=1729, eps=1e-9`).

## Lineage / why this trial exists
Trial 1 (`moe_hash 9c25d22a…`, `q_confluence=2`) closed **CLOSED_NEGATIVE_VALIDATION**
with **n=0 validation trades** — a *no-fire*, not a tested-and-lost. Cause: L1-sparsity +
budget pruned the fitted `W` to exactly **one weighted expert per regime**, but
`q_confluence=2` requires ≥2 agreeing weighted experts, so ENTER was structurally
impossible. Trial 1 halted at Gate-1; **the sealed window was NOT spent** and remains
available.

This trial corrects that structural gate so the combiner can actually trade and its
validation edge can be *tested*. This is a design correction, not selection on results:
no validation/sealed performance was observed for `q_confluence=1` before this registration.

## Hypothesis
With `q_confluence=1`, the regime-conditional MoE fires in the validation window; test
whether it clears Gate-1 (deflated significance + block-CI vs the v2.2 base) and, if so,
whether the edge transfers through the sealed and cross-asset gates.

## Trial accounting (multiple-comparisons control)
- This is **trial 2** of an effective budget **≤ `EFFECTIVE_TRIALS = 12`** (per
  `evaluate_moe.py`). DSR (`dsr_of_pairs`) deflates with `n_trials=12`; the block-CI
  quantiles already carry the family-alpha split. No additional deflation change.

## Gate order & sealed-once discipline (unchanged from trial 1)
`GATE0_FAILED_HALT → POWER_BUDGET_REFUSED → CLOSED_NEGATIVE_VALIDATION →
CLOSED_NEGATIVE_SEALED_BTC → CLOSED_NEGATIVE_TRANSFER → ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.
- **Gate-0 null calibration must pass first** (all nulls non-positive) or the run halts.
- **The sealed window (2025-07 → 2026-07) opens ONLY if Gate-0 + power + Gate-1 all pass,
  and is spent exactly ONCE.** Unlike trial 1, this config CAN reach the sealed gate.

## Data / splits (frozen, verbatim from v3)
BTC/ETH/SOL `*/USDT:USDT` 1h, `--start-ms 1577836800000 --end-ms 1782316800000`.
Train 2020→2024 (`TRAIN_END_TS_MS`), validation 2024→2025-07 (`SEALED_START_TS_MS`),
sealed 2025-07→2026-07 (`SPAN_END_TS_MS`). `--warmup 6000 --lookback 400`,
`--v22-engine promotion/engine.json`.

## Command
```
.venv/bin/python -m tools.moe_evaluate \
  --start-ms 1577836800000 --end-ms 1782316800000 \
  --q-confluence 1 \
  --out experiments/engine/moe_eval_qc1.json
```

## Honest prior / kill rule
Given the whole program's history (no OOS-valid free-OHLCV edge to date), the expected
outcome remains a **certified negative** (`CLOSED_NEGATIVE_VALIDATION` or
`CLOSED_NEGATIVE_SEALED_BTC`). A certified negative is the deliverable working. Only
`ALL_GATES_PASSED_HUMAN_DECISION_PENDING` warrants further (human) deliberation; it is
NOT an auto-promotion. This variant is the last cheap config lever on the current
3-mechanism expert set; a further negative closes the config-tuning line (next moves
would need new experts / new data, i.e. new registrations).
