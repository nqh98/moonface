# TREND SCORE REPAIR — Pre-Registration (2026-07)

**Status:** FROZEN before the registered run. One registered run; re-runs only
for demonstrated mechanical failure, documented here.

Spec: `docs/research-log/specs/2026-07-05-trend-score-repair-design.md`
Engine under test: Confluence v2.2, hash
`b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5` (LIVE,
forward clock unaffected; this lane is read-only).

## Question

Does any of exactly three audit-licensed repairs of the TREND-book scoring
order outcomes better than the frozen v2.2 scoring, out of sample, surviving
a sealed window and a veto-only replay? Promotion to v2.3 is a human decision
even on full pass.

## Registered command

    .venv/bin/python -m tools.engine_repair \
        --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000 \
        --out experiments/engine/repair_report_2026-07.json

## Frozen constants

| constant | value |
|---|---|
| TRAIN_END_TS_MS | 1688169600000 (2023-07-01T00:00:00Z) |
| SEALED_START_TS_MS | 1748736000000 (2025-06-01T00:00:00Z) |
| PURGE_MS | 604800000 (168 one-hour bars) |
| family alpha / correction | 0.05, Bonferroni over 3 -> CI quantiles 0.008333 / 0.991667 |
| OFFSET_GRID (C2) | 0, 5, 10, 15, 20 |
| CELL_FLOOR (C2) / MONO_BUCKET_FLOOR | 30 / 30 |
| panel floor / block bars / draws / seed | 200 / 168 / 1000 / 20260704 |
| candidate menu (frozen at 3) | c1_tier_merge, c2_side_vol, c3_isotonic |

## Gates (sequential)

1. **Gate 1 (validation):** paired Delta-rho (candidate minus v2.2, identical
   panel) block-bootstrap CI clean-positive at alpha/3 AND train-quartile
   bucket means weakly increasing AND n >= 200. Survivor = largest Delta-rho
   point estimate among passers; zero passers -> CLOSED NEGATIVE.
2. **Gate 2 (sealed, opened once, survivor only):** Delta-rho point estimate
   > 0 AND monotone AND n >= 200. Fail -> CLOSED NEGATIVE; no other candidate
   may ever use the sealed window.
3. **Gate 3 (replay confirm, veto-only):** identical-machinery long-only
   trend stream, candidate vs v2.2 qualifier: net R >= baseline, |max DD| <=
   baseline, 3x-cost net R > 0, n > 0. Runs after Gate 2 (sealed already
   open; not a second opening).

## Outcome interpretation

- Any CLOSED_NEGATIVE verdict: lane closed, published here, v2.2 runs out its
  clock untouched.
- ALL_GATES_PASSED_HUMAN_DECISION_PENDING: candidate is evidence-licensed for
  a HUMAN-gated v2.3 (new ENGINE_VERSION, new hash, new registration, fresh
  clock). The shadow sidecar (spec section 5) is built only in this case.

## Results (transcribed after the registered run)

Verdict: `CLOSED_NEGATIVE_GATE1`

Engine hash: `b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5`
Data fingerprint: `fedf68d49ad3ac17682cd09a1bd5f4cdd410f468ecb87dfe6949aafdcc9518df`

Segments:
- train: 21,877
- validation: 14,729
- sealed: 8,021
- dropped: 350

Panel counts:
- events: 44,977
- incomplete: 31
- skipped_extreme_vol: 380

Gate 1:
- c1_tier_merge: n=14,729, delta_rho=-0.0357, delta_ci=[-0.0995, 0.0303], monotone=true, passed=false
- c2_side_vol: n=14,729, delta_rho=0.0163, delta_ci=[-0.0203, 0.0503], monotone=true, passed=false
- c3_isotonic: n=14,729, delta_rho=-0.0357, delta_ci=[-0.0995, 0.0303], monotone=true, passed=false

Survivor: none

Gate 2: not reached
Gate 3: not reached

Stopping condition: CLOSED_NEGATIVE_GATE1. No candidate cleared the validation gate, so the sealed window was not used and no replay confirm was run.
