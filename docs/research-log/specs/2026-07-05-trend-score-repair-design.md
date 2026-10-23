# Trend-Score Repair Lane — Design

**Date:** 2026-07-05
**Status:** Approved design; feeds implementation plan
**Predecessors:** `experiments/engine/SCORING_AUDIT_2026-07.md` (Stage-1/Stage-2 published),
`experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` (UNCALIBRATED verdict),
`experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md` (FROZEN, live)

## Goal

Produce, under pre-registered evaluation, at most one repaired trend-book scoring
mechanism that is evidence-licensed to become Confluence v2.3. If no candidate
survives, close the lane NEGATIVE and let v2.2 run out its clock untouched.

The lane targets the trend book only. The revert book stays shadow-only: the
audit found NO_SIGNAL in any weighting for it, and its two contributing deriv
modules (m4_fund_ct, m5_oi_flush) did not order the book OOS under any tested
weighting.

## Evidence this design is built on (published, not re-derivable here)

- Trend hand weights are ADEQUATE; both registered weight fitters FAIL to beat
  them CI-clean. Therefore no candidate refits module weights.
- Trend ordering is real but sub-75 only: Tier-A (score ≥ 75, n = 36) inverts
  to −0.15 mean bucket R (frozen monotonicity criterion failed).
- Trend ordering concentrates in LONG and high-vol conditions; SHORT
  conditional ordering carried the CI-clean HARMFUL m4_pullback effect.
- m4_pullback is already excluded in live v2.2; its exclusion is under forward
  test and is not re-litigated by this lane.

## 1. Lane shape & governance

Read-only research lane, same pattern as the scoring-audit lane:

- Pre-registration doc `experiments/engine/TREND_SCORE_REPAIR_2026-07.md`
  frozen BEFORE any evaluation runs. It fixes: the candidate menu (§3), split
  boundaries (§2), gates and correction (§4), and the report schema.
- The live engine is untouched. v2.2 hash
  `b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5` stays
  pinned; the v2.2 forward clock keeps running.
- One registered run. Re-runs only for demonstrated mechanical failure,
  documented in the pre-reg (audit-lane precedent).
- All outcomes are published in the pre-reg doc, including full negatives.
- Promotion to v2.3 is a HUMAN decision even if all gates pass. v2.3 means new
  ENGINE_VERSION, new hash, new registration, fresh clock (per v2.2 rules).

## 2. Data & splits

- Instrument: BTC 4h, 2020-09 → 2026-06, the same panel machinery as the
  calibration diagnostic: `signal/engine/calibration.py::scoring_pass`
  (warmup 6000) with deriv columns from `deriv_history` (coverage funding
  1.0 / OI 0.9977).
- Three chronological segments via the existing `chrono_split` convention:
  - **Train** — the only place any candidate constant is fitted (thresholds,
    offsets, isotonic curve).
  - **Validation** — exactly one evaluation per candidate; Gate 1.
  - **Sealed** — the most recent segment, covering at least the final 12
    months; opened exactly once, for the sole Gate-1 survivor only.
- Exact boundary dates are frozen in the pre-reg before any panel is built
  (plan-phase detail; the ≥12-month Sealed constraint is binding).

## 3. Candidate menu (frozen at exactly 3)

Each candidate maps 1:1 to a published finding. None refits module weights.
Each candidate's constants are fitted on Train only and then frozen for its
single Validation evaluation.

- **C1 — Tier repair.** Score formula unchanged. Re-derive tier boundaries on
  Train by monotone bucket-merge (pool-adjacent-violators on bucket mean net
  R). Output: possibly-moved entry threshold and Tier-A boundary, or Tier-A
  merged into the 60–75 band. Degrades gracefully: if Train shows no
  violation, output equals current boundaries and C1 is a no-op candidate.
- **C2 — Conditional tiering.** Score formula unchanged. Tier/entry thresholds
  conditioned on (side, vol-regime) with per-condition offsets derived on
  Train. Practical effect: SHORT and low-vol setups must clear a higher score
  to qualify. Vol-regime definition reuses the engine's existing regime
  classification (`signal/engine/regime.py`); no new regime estimator is
  introduced.
- **C3 — Monotone calibration.** Replace raw-score tiers with an isotonic
  score→E[R] mapping fitted on Train. Entry requires calibrated E[R] above a
  cost-aware floor (floor derived from the frozen cost model, not fitted);
  tiers come from fixed E[R] levels. Most expressive candidate; the Sealed
  window is its real test.

## 4. Gates (sequential; all frozen in the pre-reg)

- **Gate 1 — Validation, familywise-corrected.** For each candidate: paired
  block-CI on Δρ = (candidate ordering − frozen v2.2 ordering) on the same
  Validation panel, using the `audit.block_ci` machinery. Pass requires:
  (a) Δρ CI clean-positive at α/3 (α = 0.05, Bonferroni over the 3-candidate
  menu), and (b) candidate bucket mean net R monotone non-decreasing in
  score/tier (no new inversion). Survivor = largest Δρ point estimate among
  passers. Zero passers → lane CLOSED NEGATIVE.
- **Gate 2 — Sealed, opened once.** Survivor only. Pass requires Δρ
  sign-positive and bucket monotonicity holding in the Sealed segment. Fail →
  lane CLOSED NEGATIVE; no other candidate may use the Sealed window, ever.
- **Gate 3 — Replay confirm (decision-level, veto-only).**
  `calibration.nonoverlapping_stream` replay with survivor constants over the
  full panel. This runs strictly after Gate 2, so the Sealed segment is
  already open; the full-panel replay is not a second Sealed opening.
  Compared to the v2.2 sanity baseline (130 trades, +40.14R,
  PF 1.31, max DD −21.71R, survives 3× costs at +8.51R). Pass requires:
  net R ≥ v2.2 baseline, max DD no worse than v2.2's, and 3×-cost survival.
  Gate 3 can only kill, never rank — it confirms the ordering result is not
  bracket-hostile.

All three gates pass ⇒ candidate is evidence-licensed for a human-gated v2.3
registration. Any gate fails ⇒ published NEGATIVE, v2.2 continues undisturbed.

## 5. Sidecar shadow (forward paper trail, never evidence)

- Out-of-process script `src/moonface/research/shadow_score.py` plus a CLI
  entry point. It recomputes the surviving candidate's score from the same
  candle feed and appends rows to a shadow JSONL under `experiments/engine/`.
- It imports engine code read-only and adds nothing under `signal/engine/`,
  so the frozen v2.2 hash is unaffected. Import-boundary test gets a scoped
  allow-list entry only if needed (precedent: `deriv_history.py`).
- Operation is human ops alongside the watch daemon (Deribit-collector
  precedent). Shadow output is explicitly excluded from all gates and from
  any future promotion argument; its only purpose is that a registered v2.3
  starts life with a forward record from day one.
- Built only if a candidate survives Gates 1–3. On a NEGATIVE lane outcome
  this component is not built.

## 6. Testing & verification

- TDD throughout (program norm). Unit tests:
  - C1: bucket-merge determinism; merged means monotone; no-violation input →
    identity output.
  - C2: condition-offset derivation determinism; offsets only ever raise (or
    keep) thresholds for SHORT/low-vol relative to base.
  - C3: isotonic fit monotone; fit uses Train rows only (no-lookahead test).
  - Splits: boundary hygiene — no Train bar index appears in Validation or
    Sealed panels; Sealed ≥ 12 months.
- Regression: v2.2 hash pin unchanged (existing tests in
  `test_engine_config.py` / `test_engine_calibration_pass.py` must stay
  green).
- Verification checklist before the registered run: full suite green;
  read-only diff vs `signal/engine/`, journal, promotion code = 0 lines;
  no attribution trailers in commits.

## Known risks (stated up front)

- Same-instrument risk: the repairs are evaluated on the instrument that
  produced the findings, so they could fit the diagnostic's noise. Defenses:
  Train-only fitting, α/3 familywise correction, single-opening Sealed
  window, veto-only replay gate.
- Tier-A n = 36: C1 may be "repairing" noise. The monotone merge degrades to
  identity when Train shows no violation, so the failure mode is a no-op, not
  a fabricated change.
- Replay n ≈ 130 is noisy. That is exactly why Gate 3 is confirm/veto only
  and never selects among candidates.
- Watch-for from the last two lanes: implementers bending plan-test
  expectations into code (audit LOO short-circuit) or silently skipping
  planned tests (v2.2 decide()-level tests). The implementation plan must
  carry its test expectations verbatim and the verifier must diff tests
  against the plan.

## Out of scope

- Revert-book redesign (NO_SIGNAL published; deriv-contributor follow-up is a
  separate future lane if ever).
- Any change to module internals, module weights, macro gate, CT discipline,
  or exit logic.
- Any interim peeking at the live v2.2 forward record to steer this lane.
