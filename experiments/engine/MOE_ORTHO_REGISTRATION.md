# Regime-MoE — Orthogonal-Expert Registration (Trial 3)

**Registered:** 2026-07-10 (BEFORE any evaluation of this config).
**Expert set (frozen):** BREAKOUT, PULLBACK, REVERSION, FUNDING, OI.
**Frozen constants:** `FUNDING_CAP = 0.01`, `OI_LOOKBACK = 24`.
**Config:** `MoeConfig(q_confluence=1)`; all other fields default
(`tau=0.35, m_per_weight=50, shrink_snr=1.0, l1_frac=0.10, norm_mode="rank", seed=1729, eps=1e-9`).
**Frozen identity_hash:** `c4840e61eba4738d21d4aab52385c5b3a88ea5aadd332ce02f6249bd91185e76`

## Lineage
Trials 1 (`q=2`, no-fire) and 2 (`q=1`, fires n=353 but flat, CI straddles 0) both
CLOSED_NEGATIVE_VALIDATION; sealed UNSPENT; config-tuning line closed. This trial adds two
orthogonal (non-price) experts. `q_confluence=1` is carried forward so the new experts are
actually tested (trial 2 proved `q=2` risks a structural no-fire).

## Hypothesis
Regime-conditioned weighting of funding (crowd-fade) and OI (confirmation) contributes edge
the price mechanisms lacked. **Honest prior: negative** (OI standalone dead per
`oibuild-mechanism-verdict`; funding-fade transfer dead per `funding-fade-transfer-results`).
The open question is regime-conditioned combination, not either signal alone.

## Trial accounting
Trial 3 of `EFFECTIVE_TRIALS<=12`; DSR deflates with `n_trials=12`.

## Gate order / sealed-once (unchanged)
`GATE0_FAILED_HALT -> POWER_BUDGET_REFUSED -> CLOSED_NEGATIVE_VALIDATION ->
CLOSED_NEGATIVE_SEALED_BTC -> CLOSED_NEGATIVE_TRANSFER -> ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.
Gate-0 must pass first; sealed opens ONLY if Gate-0+power+Gate-1 pass; sealed spent ONCE
(currently UNSPENT; this config CAN reach it).

## Implementation note (pre-run fix, in scope of this registration)
While wiring the 5-expert set through Gate-0, `null_calibration`'s three null generators
(`iid_shuffle`, `sign_flip`, `phase_randomize`) were found to share one sequentially-mutated
`random.Random` — each generator's entropy draw scales with `len(experts)` (including
no-fire experts), so adding FUNDING/OI shifted the RNG state consumed by later generators
for unrelated (price) experts, for no statistical reason. Verified empirically: the
single-draw false-positive rate for a fully-null 5-expert panel measured ~60% (5/8 seeds)
under the coupled RNG vs. ~13% (1/8, matching the expected single-draw base rate for the
existing CI construction) once each generator gets its own independently-seeded RNG
(`random.Random(f"{cfg_moe.seed}:{label}")`). Fixed in the same commit as the bundle-input
`build_moe_report` change (Task 3); does not alter any gate's accept/reject criterion, only
isolates the entropy source per generator so results no longer depend on the expert set's
size or dict order.

## Implementation note 2 (pre-run fix, discovered on first execution attempt)
The first run attempt failed at data-load time: `ETHUSDT`/`SOLUSDT` `sum_open_interest`
history only starts 2021-12-01 (vs. BTC's 2020-09-01), so fetching the full
2020-01-01->2026-07-10 span for ETH/SOL trips `_check_coverage`'s 80% floor (actual
coverage ~70.4%). Since ETH/SOL only ever contribute to `gate3_transfer`, which is
evaluated solely within the sealed window (`W` is fit on BTC alone), the CLI now narrows
ETH/SOL's *fetch* range to `SEALED_START_TS_MS - PURGE_MS - lookback*timeframe_ms - 90d`
(`tools/moe_evaluate.py::_bundle_start_ms`) instead of the full requested range. BTC's
fetch range is unchanged. This does not touch `identity_hash` (start/end-ms are not part
of the frozen trial identity) or any gate's accept/reject criterion — it only changes how
much history is *requested* for two assets that are never evaluated outside the sealed
window.

## Command
```
.venv/bin/python -m tools.moe_evaluate --start-ms 1577836800000 --end-ms 1782316800000 \
  --q-confluence 1 --experts all --out experiments/engine/moe_eval_ortho.json
```

## Kill rule / terminal
Expected `CLOSED_NEGATIVE_VALIDATION` or `_SEALED_BTC`. Only `ALL_GATES_PASSED` warrants
(human) deliberation; never auto-promote. A negative closes the free-data orthogonal-expert
line.
