# funding_fade_fwd — STATUS

- **Phase:** SIGNED OFF — FROZEN (D-gate cleared, spec §7.3). Amendment
  window CLOSED PERMANENTLY. The program is untouchable until the verdict
  trigger fires: one forward run, one verdict, terminal either way.
- **Sign-off date:** 2026-07-14

## Frozen at sign-off (the pin)

| Item | Value |
|---|---|
| identity_hash | `4c481e88f3076bdc18cf198c78ceaeed9ba9db1961234985734bc2d15febd1d0` |
| Pipeline commit | `0e3fef3a41aa686f9932e94fc0518f2afe438335` |
| DD budget (KILL) | **−64R** (cumulative forward R ≤ −64R at any point → KILL) |
| Verdict-trigger N | **108** completed forward trades |
| Calendar floor | **12 months** from sign-off |
| Trigger rule | **later-of** N=108 and 12 months |

identity_hash regenerates from the pinned commit with
`.venv/bin/python tools/funding_fade_fwd.py identity --dd-budget-r -64
--n-trades 108 --months 12` (canonical JSON over rules + every frozen
parameter; MOE_ORTHO convention). All PIPELINE_FREEZE_PLAN.md code paths
are committed at the pinned hash and clean at sign-off.

## Sign-off rationale (for the record)

- **DD budget −64R.** With the three-condition rule as primary
  discriminator, the DD rule is a catastrophic backstop only. −64R is the
  sole candidate where KILL keeps clean semantics: P(hit | zero-edge) 8.0%
  vs 27.6% at −40R (REGISTRATION_DRAFT §4). A budget that would have killed
  the known pre-cutoff path (peak-DD −32R, cumulative min −15.26R) is
  incoherent with the premise; −64R clears it with margin.
- **N=108.** Matches the program's honest power scope: a tail-sized claim
  (≈+1.1R), MDE ~0.54R at n=108, verdict ~mid-2027. Coherent with the
  1.5–2.5y edge-death detection bound that makes multi-year public-data
  formula windows incoherent — so N=485/990 were declined despite higher
  nominal power. **NO-EDGE at 12 months is the expected outcome unless the
  edge is tail-sized; that outcome is acceptable and pre-committed.**
- **Deployability caveat (acknowledged at sign-off):** EDGE FOUND under a
  −64R research budget does NOT by itself establish deployability under
  bounded risk. That is a separate, subsequent decision outside this
  program.

## Frozen success / kill machinery (unchanged from the draft)

- **Success (EDGE FOUND requires ALL THREE, Amendment 2):** (i) forward
  cumulative R > 0; (ii) 95% moving-block-bootstrap CI (block 10, 10,000
  resamples, seed 42) on per-trade expectancy excludes 0 from above;
  (iii) forward cumulative R STRICTLY exceeds the null p95 of 200 same-window
  funding-shuffle nulls (seeds 0–199, `sorted[min(n-1,ceil(0.95n))]`, strict
  exceed) computed once at verdict on the frozen pipeline.
- **KILL:** cumulative forward R ≤ −64R at any point.
- **VOID:** >5% of the forward window unreconstructible; or BTC USDS-M
  delisting / structural funding-mechanism change (dated note).
- **Null guard (machinery validation):** 192/200 nulls FAIL the
  three-condition rule → guard_ok. Circularity acknowledged (Amendment 2,
  condition 3): the ≤5% pass rate holds by construction under condition (iii)
  and is not independent evidence. The same guard, same seeds, re-runs on the
  pinned commit before the forward result is trusted.
- **Strategy formula:** verbatim from the original row
  (REGISTRATION_DRAFT §1); frozen.
- **Forward window start:** 2026-06-10T08:00:00Z (Amendment 1). Accrued
  unseen since; never observed by any drafting/sign-off phase
  (clamp-enforced; verified again at sign-off 2026-07-14).

## Forward run (single spend, from the pinned commit)

Per PIPELINE_FREEZE_PLAN.md §"Forward-run data plan": at trigger, one
retroactive fetch, isolated cache, VOID-rule-2 reconstructibility audit
BEFORE any performance aggregation, then the 200-seed null benchmark and the
three-condition verdict computed in the same execution, verdict written
directly. Re-runs require a written VOID/amendment note — no silent second
spend. No code changes to any pinned path between sign-off and verdict; an
unrelated repo change that forces one is a spec §5 escalation, human-decided.

## Amendment log (closed)

- AMENDMENTS.md — Amendment 1 (completed-candle re-baseline, Escalation-1
  ruling a) and Amendment 2 (null-calibrated three-condition success
  criterion, Escalation-2 ruling A). Both ruled and applied before any
  freeze; no forward data observed. Window closed permanently at sign-off.
- OBSERVATIONS.md — random-entry bracket regime finding (non-gating, opens
  no lane).
- Data-hygiene incidents: none. The Escalation-1 04:00–08:00Z boundary sliver
  was acknowledged in the Amendment-1 ruling (assigned to the baseline side).
