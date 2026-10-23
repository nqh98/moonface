# Price-Axis Geometry Reformulation — Coverage Audit

- **Date:** 2026-07-14
- **Status:** analysis only. NOT a registration, NOT an edge claim. NO_CLAIM.
- **Analyzes:** the two-axis (price × time) geometric reformulation of the gravitational
  market-universe model (`docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md`, D1).
- **Authoritative records consulted:** `experiments/forced_flow/PILOT_VERDICT.md` +
  `verdict.json` (KILL, commit 5d519e6, terminal), `experiments/forced_flow/PILOT_COINM_REGISTRATION.md`
  (FROZEN), `experiments/forced_flow/STATUS.md`, `experiments/forced_flow/STAGE0_FEASIBILITY.md`,
  D1, `experiments/microscope/FINDINGS.md`, `experiments/sse/` (REGISTRATION.md,
  gate0_verdict.json), `experiments/liqladder/`, `experiments/euphoria_fade/RESULTS.md`,
  `experiments/lane1_twap/`, `experiments/newdata/liquidations/manifest.json`.

## Verdict (Q3): `FULLY_COVERED`

Every testable construct the two-axis geometry implies is already covered by an existing
verdict (≥50% overlap → VOID), banned outright, or blocked on data that does not exist
keylessly today. No construct is <50% covered *and* computable from keyless data available
now. The prior expectation stated in the audit request (`PRESENTATION_ONLY` or
`FULLY_COVERED`) holds; there is nothing new here, and recording that plainly is the point.

## Dark-matter honesty clause (carried per spec §2.5)

Most of the mass governing price is unobservable from a retail seat. The two-axis geometry
does not change this: it constrains where observable bodies may sit, not how much of the
mass is observable.

## 1. The reformulation

The universe has exactly two axes, price and time. Every field source must either project
onto the price axis (mass waiting at a price level) or accumulate along the time axis
(pressure per interval regardless of price location); anything projecting onto neither has
no coordinates and does not exist in the model. Bodies are stationary: wells sit at
liquidation-trigger prices and discharge/empty on contact; gamma sits at option strikes;
funding ratchets per 8h interval. The price particle is the only moving object.

The geometry is correct as a description of the model's coordinate system, and it makes one
thing sharp (see §3): the COIN-M pilot's Gate 0 — "does the particle fall toward the wells"
— was a complete test of the model's currently measurable content, and the answer was KILL.

## 2. Q1 — Construct enumeration and overlap audit

Rule applied: ≥50% mechanism overlap with an existing verdict → VOID. Overlap percentages
are estimates of *mechanism* overlap (same underlying causal claim), not feature overlap.

| # | Construct implied by the geometry | Axis | Covering record | Est. overlap | Ruling |
|---|---|---|---|---|---|
| C1 | Realized liquidation-well response (particle falls toward wells that discharged) | price | COIN-M pilot KILL — 181 episodes, powered (3 qualifying buckets), spread 0.60–0.67× of both null p97.5 thresholds, iid guard clean, `experiments/forced_flow/PILOT_VERDICT.md` (commit 5d519e6, one cycle, spent, terminal) | **100%** (COIN-M scope) | KILLED in scope. USDⓈ-M variant is the already-open main lane, blocked to ~2027-01-09 (`STATUS.md`) with a downgraded prior — not a new construct |
| C2 | Forward liquidation-density map by price level (exact: mass waiting at not-yet-reached prices) | price | D1 §2 computability matrix, class **(d)**: requires position/leverage-distribution data with **no confirmed keyless source** | n/a — untestable | BLOCKED. Inherits the class-(d) blocker; NOT a new opportunity (full treatment in §3) |
| C3 | Forward well ladder *estimated* from OI deltas + price path | price | `experiments/liqladder/` — H2 liq-ladder magnet, CLOSED NEGATIVE 2026-07-02 (this was precisely an estimated forward liquidation ladder tested as a price attractor); reinforced by `oibuild` (mechanism does not exist) and `liqrev` (OI dead both directions) | **≥80%** | VOID |
| C4 | Well detection from candle-derived proxies | price | `experiments/lane1_twap/` — candle liquidation proxies falsified (max effect-Z 1.03) and **banned** program-wide (D1 §5) | n/a — banned | BANNED |
| C5 | Strike-ladder dealer-gamma profile (stationary mass at strikes) | price | D1 §1/§2: CLEAR of prior nulls but class **(d)** — BLOCKED on Deribit chain accrual (collector live 2026-07-03, readiness ~2027-01) | 0% covered, 100% blocked | BLOCKED. The geometry restates what an options chain already is (strikes are price-stationary by construction); it does not unblock anything |
| C6 | Time-axis funding pressure (per-8h ratchet, cumulative bleed, bleed slope — any framing) | time | Axis F **VOID** per D1 §1: microscope crowding axis (mean funding_z/oi_chg_z, n=1838, INDISTINGUISHABLE_FROM_NULL, `experiments/microscope/FINDINGS.md`); SSE Track L (both cells FAIL at Gate 0, `experiments/sse/gate0_verdict.json`); regime_moe trial 3 (FUNDING expert never selected); `oibuild`; `price_oi_divergence` (stage-1 negative) | **≥50%** | VOID. The time-axis framing is a re-labeling of the identical mechanism — forced dollar bleed per funding interval. Per the audit's own constraint, a re-framing of a voided mechanism is still the voided mechanism; the framing presents no genuinely different construct |
| C7 | Time × price interaction: time-axis pressure modulating well discharge (e.g., funding-charged wells discharge harder) | both | Conditioning side inherits Axis F VOID (C6); well side is KILLED (C1) or BLOCKED (C2). Architecturally ≥50% overlap with regime_moe trial 3 (FUNDING+OI experts conditioning a base signal, CLOSED_NEGATIVE_VALIDATION 2026-07-10) | **≥50%** on each leg | VOID / BLOCKED on both legs. An interaction term cannot smuggle a voided axis back in |
| C8 | Other time-axis accumulators the geometry admits: basis carry to expiry; calendar-time pressure; options theta | time | Basis: `experiments/basis/` REJECTED (all 4 cells fail OOS, stopping condition B). Calendar: `experiments/calseason/` CLOSED NEGATIVE (no cell clears \|Z\|>3). Theta: options data — same Deribit blocker as C5 | ≥50% / ≥50% / blocked | VOID / VOID / BLOCKED |
| C9 | Emptied-well hysteresis: past discharge sites as persistent S/R on revisit | price | Excluded **by the geometry itself** — the discharge rule says an emptied well exerts no further pull. Even inverting that rule: COIN-M archive is spent (any touch is automatically void); USDⓈ-M needs the ~2027-01 accrual; proxies banned (C4) | n/a | Self-excluded by the model; untestable today regardless |
| C10 | The nonexistence rule: constructs projecting onto neither axis (regime labels, state-space cluster geometry) are outside the model | — | Consistent with the microscope null (forward R does not stratify by regime, n=1838) and SSE CLOSED (state-space Gate-0 FAIL, era sign-flips) | n/a | Interpretive only. The rule retroactively rationalizes recorded nulls; it generates no test |

No enumerated construct is simultaneously (<50% covered) and (computable from keyless data
today). C2 and C5 are the only constructs with genuinely uncovered content, and both carry
hard data blockers already recorded in D1.

## 3. The realized/forward distinction (the sharpest candidate)

The COIN-M pilot tested **realized** liquidation response: episodes triggered by bursts that
had already printed, outcome measured forward from the burst. The geometric model's wells
are **forward-looking**: mass waiting at trigger prices not yet reached. Is this distinction
a new opportunity?

**(a) Is it empirically meaningful?** Yes, in principle. "Price accelerates toward a dense
well region before contact" and "price continues after a discharge" are different causal
claims with different feature requirements. The distinction is real, not verbal.

**(b) Is it testable with keyless data available today?** **No.** Ruling: **(b) governs.**

- The *exact* forward-density map requires the position/leverage distribution across market
  participants — D1 computability matrix class (d), no confirmed keyless source. The
  construct inherits that blocker wholesale.
- The *estimated* forward map (inferring trigger ladders from OI changes and price) was
  already built and tested: `liqladder` — the H2 liquidation-ladder magnet hypothesis —
  CLOSED NEGATIVE 2026-07-02, on a datasource (`oibuild`, `liqrev`) that is dead in both
  directions. Estimated overlap ≥80%: same mechanism, same data class, tested as the same
  "price attracted to forward liquidation mass" claim.
- The *proxy* route (inferring wells from candles) is banned (`lane1_twap`).
- The spec's own §2.2 fallback for exactly this blocker was "model from realized-flow
  response instead" — which is what the pilot did, and the pilot returned KILL.

So the forward-looking well is not a new opportunity: its exact form is class-(d) blocked,
its estimated form is already killed, its proxy form is banned, and its sanctioned fallback
is the pilot that just returned KILL. The distinction is meaningful and simultaneously
moot.

## 4. Q2 — Does the geometry change the two open doors?

**(a) Main USDⓈ-M forced_flow lane (~2027-01-09).** No substantive change. The planned
`WellField` quantities (`liq_count`, `liq_imb`, `liq_burst_z` — D1 §3) are already
price-axis realized-well features; the Gate-0 battery (label shuffle, circular shift, iid
guard) is axis-agnostic; the forward-density map stays out of scope (class d); Axis F stays
excluded from the architecture. The geometry's discharge/re-arm intuition is *already
encoded* in the pilot's episode re-arm rule (6 sub-threshold bars before a new entry). At
most, the discharge rule is one candidate consideration when that registration is frozen in
~2027-01 — under its own overlap audit, as D1 §4 already requires. Nothing changes now.
**This is presentation only.**

**(b) Gamma/curvature lane (Deribit).** No change at all. An options chain is natively a
price-axis strike ladder; the geometry restates the data's shape, it does not add a feature,
a gate, or a null. The lane remains blocked on accrual (~2027-01) and remains subject to its
own future overlap audit and registration. **This is presentation only.**

## 5. Q3 — Verdict and honesty framing

**`FULLY_COVERED`.** Every construct the two-axis geometry implies is void (C3, C6, C7,
C8-basis, C8-calendar), banned (C4), killed in scope (C1/COIN-M), blocked (C2, C5,
C8-theta, C1/USDⓈ-M until ~2027-01-09), self-excluded (C9), or interpretive (C10).

The honest reading, carried per the request's framing: the two-axis observation is
geometrically correct, and its principal value is clarifying why the COIN-M pilot was a
*complete* test of the model's currently measurable content. "Does the particle fall toward
the wells" was precisely Gate 0; the answer, on 181 powered episodes with a clean harness
(iid guard failed on null as required, split-half consistent), was **KILL**. The
reformulation does not open an escape from that verdict, and this audit confirms it was not
one. Nothing new here — and that is the correct, ledger-preserving result.

## 6. Constraints honored

- COIN-M archive untouched; no re-analysis, no parameter variants.
- Axis F remains VOID; the time-axis framing was audited (C6) and does not resurrect it.
- No candle-derived liquidation proxies considered admissible (C4).
- No contact with the live v2.2 engine (hash `b4924f8e…`), no sealed data, no lockboxes.
- No code, no runs, no downloads, no new registrations. This document is the sole
  deliverable. Next decision points are unchanged: USDⓈ-M readiness ~2027-01-09 and Deribit
  readiness ~2027-01, each requiring its own overlap audit, frozen registration, and human
  sign-off (D-gate pattern).
