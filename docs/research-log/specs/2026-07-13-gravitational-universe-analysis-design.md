# Gravitational Universe Model — Analysis & Pilot-Registration Design

- **Date:** 2026-07-13
- **Source spec:** `docs/research-log/concepts/gravitational_universe_model_spec.md` (concept spec, not a registration)
- **Status:** design approved in session; deliverables not yet written
- **Scope ruling (user, 2026-07-13):** deliver exactly D1 → D2 → D3 → D4 below, in order, then STOP.
  No fieldmap code (rejected: no code that idles for 6 months). No runs. No signal emission.

## Context that constrains everything

`experiments/forced_flow/STAGE0_FEASIBILITY.md` (commit 9a85ecf, 2026-07-13) already decided the
spec's empirical questions:

- **Axis L (liquidation prints):** overlap-CLEAR (0% — genuinely new data) but BLOCKED: zero
  keyless BTCUSDT history exists anywhere; the forward collector had never run. It was started
  2026-07-13 (reconnect fix + flock cron watchdog, commit 1ccae38); readiness (≥180 d, ≥200
  clusters, coverage ≥0.90) lands ~2027-01-09 at the earliest.
- **Axis F (funding × OI bleed):** **VOID** — fails the ≥50% overlap clause against
  microscope (crowding axis, INDISTINGUISHABLE_FROM_NULL at n=1838), SSE Track L, regime_moe
  trial 3, oibuild, price_oi_divergence. Excluded from every downstream plan. The spec's
  "computable today" claim is true of the data, false of admissibility.
- **Gamma (§2.4):** overlap-CLEAR but blocked on Deribit chain accrual (~2027-01). Stub only.
- **The referenced `forced_flow_lane_preregistration.md` does not exist in the repo** — the
  draft was conversation-only. STAGE0_FEASIBILITY.md is the authoritative record.
- The only near-term empirical read on the gravity-well mechanism is the frozen Binance Vision
  COIN-M archive: `cm/daily/liquidationSnapshot/BTCUSD_PERP/`, 2023-06-25 → 2024-10-14,
  472 files, coverage 0.987, throttle-sampled.

## D1 — Analysis document

`docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md`, six parts:

1. **Overlap audit** (spec §4.1) per field component, with file references:
   §2.2 Axis L CLEAR/blocked; §2.3 Axis F VOID; §2.4 gamma CLEAR/blocked-stub;
   §2.5–2.7 (dark matter, Hawking decay, WAIT) documented as honesty clauses and
   re-validation cadence, not testable field components.
2. **Computability matrix** (spec §4.2): each field quantity → (a) computable today /
   (b) after Stage-0-confirmed history / (c) blocked on forward accrual / (d) blocked on paid
   or Deribit data. Headline: **nothing gate-able is computable today**.
3. **Fieldmap architecture on paper** (spec §4.3): interface signatures only — field-source
   protocol, per-bar `FieldState`, stratification consumer that would plug into the forced_flow
   pipeline, gamma stub interface; placement under `research` layer per
   `tests/test_import_boundaries.py` conventions. Zero code, by explicit scope ruling.
4. **Execution plan keyed to readiness dates:** now → COIN-M pilot decision (D2/D3);
   ~2027-01 → USDⓈ-M Axis-L readiness + Deribit gamma; only then Gate 0 of the main lane.
   Earliest possible main-lane verdict follows the collector readiness gate.
5. **Risk register** (spec §4.6): the ways the layer regresses into belief-weighted scoring
   (hand-tuned well-influence radii, arbitrary mass-decay constants, post-hoc body additions,
   proxy substitution, parameter menus) and the guardrail: every free parameter frozen in a
   registration before any run, else the lane is void.
6. **Corrections to the source spec:** missing prereg file (above); §4.4 visualization
   deprioritized outright — its precondition (non-null forced_flow verdict) is unreachable
   before ~2027.

## D2 — COIN-M pilot registration DRAFT

`experiments/forced_flow/PILOT_COINM_REGISTRATION.md`. Design only — no run, no pilot code
until D3 sign-off. Frozen content (approved in session):

- **Claim:** BTCUSD_PERP forward returns may stratify by realized forced-liquidation flow
  (cluster presence, direction, imbalance) — a directional read on the gravity-well mechanism.
- **Data (keyless Binance Vision only):** `cm/daily/liquidationSnapshot/BTCUSD_PERP/`
  2023-06-25 → 2024-10-14 with exact-duplicate-row dedupe; `cm` klines BTCUSD_PERP 1h, same
  window. No funding, no OI (Axis F void). No candle-derived proxies (banned).
- **Features (throttle-robust only; summed notional banned):** per 1h bar
  `liq_count`; `liq_imb = (buy_liq_count − sell_liq_count) / max(total, 1)`;
  `liq_burst_z = z(log(1 + liq_count))` on a trailing 30-day causal window.
- **Observation unit:** cluster-entry episode — first bar with `liq_burst_z ≥ 2.0` after ≥6
  consecutive bars below (re-arm rule). Episode direction = sign of `liq_imb` on the entry bar.
- **Outcome:** BTCUSD_PERP log return over **H = 24 × 1h bars** from episode-entry close.
  Single frozen horizon.
- **Stratification:** direction × magnitude-tercile buckets (≤6), magnitude = `liq_burst_z`
  at episode entry, terciles computed over all episodes; power floor n ≥ 30 per
  bucket; spread = top-bucket mean − bottom-bucket mean. Fewer than 2 qualifying buckets →
  `UNDERPOWERED_KILL` (pre-committed; no threshold re-tuning to manufacture power).
- **Gate-0 null battery (all three required):**
  1. label-shuffle, 1000 iterations, real spread > p97.5;
  2. circular-shift of the liquidation series vs price, 1000 shifts, real spread > p97.5;
  3. **iid null-calibration guard:** the frozen pipeline on directionless iid-resampled
     returns must FAIL the gate; if it passes → `SUSPECT_HARNESS`, no hypothesis
     interpretation (vol_compression lesson).
- **Single-era honesty:** no lockbox exists or is claimed. Split-half sign check
  (2023-06-25→2024-02-15 vs 2024-02-16→2024-10-14) is supporting evidence only, never a pass
  condition.
- **Evidence-weight clause (verbatim, user-mandated):** "This pilot runs on a different
  instrument (BTCUSD_PERP COIN-M), a single era, with throttled magnitude. Its only possible
  outcomes are KILL (kills the gravity-well hypothesis) or WEAK SUPPORT (updates the prior for
  the main USDⓈ-M lane). It CANNOT validate the hypothesis, and no result from it licenses any
  promotion, signal emission, or 'EDGE FOUND' claim."
- **No-promotion clause:** if the pilot passes, the sole next step is running the main
  forced_flow lane when USDⓈ-M data matures; nothing connects to the live v2.2 engine
  (hash b4924f8e…), Telegram, or any decision-emitting journal.
- **Terminal discipline:** one cycle, one verdict written once; any post-run parameter change
  voids the lane.

## D3 — Sign-off gate

After D2 is written, STOP and present the registration to the user. The pilot does not run and
no pilot code is written until the user approves the frozen registration.

## D4 — STATUS.md

`experiments/forced_flow/STATUS.md`, one page: what is measurable today (nothing gate-able;
funding/OI caches healthy but Axis F void); what is blocked until when (USDⓈ-M Axis L
~2027-01-09, collector restarted 2026-07-13 with reconnect + flock fixes; Deribit gamma
~2027-01); and the single next decision point (user sign-off on D2).

## Error handling / discipline

- No sealed data is touched by any deliverable; the lockbox remains unspent.
- The docs carry the dark-matter honesty clause (§2.5) and the NO_CLAIM convention where
  applicable.
- Where the physics metaphor and a measurement disagree, the data wins and the analogy is
  amended or dropped (spec §5).

## Testing

Docs-only work: verification = internal-consistency review of the three documents against
STAGE0_FEASIBILITY.md and this design (no contradicting dates, verdicts, or parameters), plus
confirmation that no code, config, or registration outside the three files is touched.
