# Gravitational Market-Universe Model — Analysis (D1)

- **Date:** 2026-07-13
- **Analyzes:** `docs/research-log/concepts/gravitational_universe_model_spec.md` (concept spec)
- **Authoritative empirical record:** `experiments/forced_flow/STAGE0_FEASIBILITY.md` (commit 9a85ecf)
- **Status:** analysis and planning only. NOT a registration, NOT an edge claim. NO_CLAIM.
- **Scope ruling (user, 2026-07-13):** deliverables are this document, a COIN-M pilot
  registration DRAFT (`experiments/forced_flow/PILOT_COINM_REGISTRATION.md`), and
  `experiments/forced_flow/STATUS.md`. No fieldmap code until data exists. No runs.

## Dark-matter honesty clause (spec §2.5 — mandatory in all outputs of this line)

Most of the mass governing price is unobservable from a retail seat (OTC flow, whale wallets,
institutional desks). Every prediction produced by this model line has a structurally low
accuracy ceiling: the map covers only the luminous fraction of a dark universe.

## 1. Overlap audit (spec §4.1)

| Spec component | Construct | Prior nulls checked | Verdict |
|---|---|---|---|
| §2.2 gravity wells (Axis L) | real liquidation prints: cluster presence, direction, imbalance | `lane1_twap` (candle proxy only — proxies banned, real prints never tested); `liqladder`/`liqrev` (OI, not prints); `forced_error` Setup 3 (DEFERRED, never run); microscope/SSE (no liquidation input) | **CLEAR — 0% overlap. But DATA-BLOCKED** (see §2) |
| §2.3 radiation pressure (Axis F) | funding_rate × OI dollar bleed | microscope crowding axis = mean(funding_z, oi_chg_z), n=1838, INDISTINGUISHABLE_FROM_NULL; SSE Track L (both cells CLOSED at Gate 0); regime_moe trial 3 (FUNDING expert never selected; OI CI straddles 0); `oibuild` (mechanism does not exist); `price_oi_divergence` (stage-1 negative) | **VOID — ≥50% mechanism overlap.** Excluded from every downstream plan. The spec's "computable today" is true of the data, false of admissibility |
| §2.4 curvature (dealer gamma) | dealer-gamma sign/magnitude from options chains | no prior options-based lane exists | **CLEAR — but BLOCKED** on Deribit chain accrual (collector live 2026-07-03, readiness ~2027-01). Interface designed as stub only |
| §2.5 dark matter | unobservable flow | not a testable construct | honesty clause (above), carried in all outputs |
| §2.6 Hawking evaporation | edge decay | consistent with recorded precedent: all three `practical_full` finalists sign-reversed in the 2025-03→2026-06 sealed window | not a field component; mandates re-validation cadence + decay monitoring in any future validated map |
| §2.7 WAIT-as-vacuum | zero-gradient region | untestable until at least one field axis exists | hypothesis noted, NOT assumed; no connection drawn to the live v2.2 WAIT streak |

## 2. Computability matrix (spec §4.2)

Classes: (a) computable today from repo/keyless data · (b) computable after confirmed
historical access · (c) blocked on forward accrual · (d) blocked on paid/Deribit data.

| Field quantity | Class | Notes |
|---|---|---|
| Rolling net liquidation imbalance, BTCUSDT | **(c)** | forward collector restarted 2026-07-13 (commit 1ccae38); readiness (≥180 d, ≥200 clusters, coverage ≥0.90) ~2027-01-09 |
| Liquidation burst intensity vs rolling median, BTCUSDT | **(c)** | same; features must be throttle-robust (counts/direction, never summed notional — WS feed is 1 order/sec sampled) |
| Forward liquidation-density map by price level | **(d)** | requires position/leverage distribution data with no confirmed keyless source. Per spec §2.2 fallback: model from realized-flow response instead — which is exactly the (c)/pilot rows |
| COIN-M BTCUSD_PERP realized cluster features | **(a)** | keyless Binance Vision archive 2023-06-25 → 2024-10-14 (472 files, coverage 0.987, frozen, throttle-sampled). Pilot only — different instrument, single era |
| Funding-bleed intensity / cumulative bleed / slope | data (a), axis **VOID** | 6 y funding + 5-min OI cached; inadmissible as a stratification axis (§1) |
| Dealer gamma sign/profile | **(d)** | Deribit chain readiness ~2027-01, or paid history |

**Headline: nothing gate-able is computable today.** The only near-term empirical read on the
gravity-well mechanism is the COIN-M pilot (D2), which requires human sign-off (D3).

## 3. Fieldmap architecture — on paper only (spec §4.3)

Zero code now (user ruling: no code that idles for six months). Future placement:
`src/moonface/research/fieldmap/` under the `foundation → signal → research` layering enforced
by `tests/test_import_boundaries.py`. Interfaces, to be implemented only when an axis has data:

- `FieldSource` (protocol): `name: str`; `ready() -> bool` — reads the source's readiness
  manifest (e.g. `experiments/newdata/liquidations/manifest.json`), never assumes a collector
  ran; `series(start, end) -> DataFrame` of per-bar field quantities.
- `WellField` (dataclass, per bar): throttle-robust realized-liquidation quantities
  (`liq_count`, `liq_imb`, `liq_burst_z`) — the forward-density map is out of scope (§2 class d).
- `CurvatureSource` (stub): same protocol; `ready()` returns `False` until Deribit readiness;
  adding it later must not re-architect consumers (spec §2.4 requirement).
- Stratification consumer: `stratify(episodes, field) -> buckets` feeding the forced_flow
  Gate-0 harness (label-shuffle + circular-shift + iid guard) — the pilot (D2) freezes the
  first concrete instance of this design.
- No radiation/Axis-F component exists in the architecture (VOID, §1).

## 4. Execution plan keyed to readiness dates (spec §4.5, corrected)

The spec's proposed order ("Stage 0 → Axis F → Axis L → Gate 0") is invalidated: Stage 0 fired
the kill rule on Axis L data and Axis F is void.

| When | Action |
|---|---|
| Now | D1 analysis + D2 pilot registration draft + D4 status page → **D3 human sign-off gate** (hard stop) |
| If D3 approved | build + run COIN-M pilot per frozen registration; one cycle, one verdict |
| Continuous | monitor USDⓈ-M liquidation accrual (`manifest.json`) and Deribit chain accrual; verify the collector is actually running, not merely shipped |
| ~2027-01-09 | USDⓈ-M Axis-L readiness → freeze main forced_flow registration (Axis L only) → Gate 0 |
| ~2027-01+ | gamma axis becomes designable (own overlap audit + registration first) |

Earliest possible main-lane verdict: shortly after the ~2027-01-09 readiness gate. Earliest
possible pilot verdict: shortly after D3 sign-off.

## 5. Risk register (spec §4.6) — how this becomes belief-weighted scoring again

| Risk | Guardrail |
|---|---|
| Hand-tuned well-influence radii / windows | every radius, window, threshold frozen in a registration before any run; post-run change voids the lane |
| Arbitrary mass-decay constants | no decay parameters exist in v1; any future addition needs its own frozen registration |
| Post-hoc body addition after a null | carried-over hard constraint: null ⇒ archived with the verdict, no rescue by adding bodies |
| Proxy substitution when data is blocked | banned; `lane1_twap` falsified candle proxies (max effect-Z 1.03) |
| Optimization loops over field parameters vs outcomes | banned (spec §5); single frozen config, one run, one verdict |
| Visualization becoming an implicit signal | §4.4 visualization deprioritized outright until a non-null forced_flow verdict (unreachable before ~2027); NO_CLAIM banner mandatory if ever built |
| Metaphor overriding measurement | spec §5 rule stands: data wins, analogy is amended or dropped |
| Silent collector failure (learned 2026-07-13) | before freezing any registration on forward data, verify accrual via output dir + manifest, never via "the tool was shipped" |

## 6. Corrections to the source spec

1. The referenced `forced_flow_lane_preregistration.md` **does not exist in the repo** — the
   draft was conversation-only. `experiments/forced_flow/STAGE0_FEASIBILITY.md` is the
   authoritative record of the lane's Stage 0.
2. §4.5's execution order is invalidated (see §4 above).
3. §4.4 visualization is deprioritized outright; its precondition cannot be met before ~2027.
4. §2.3's "computable today with zero new data" holds for the data, not the axis: Axis F is
   VOID under the program's own ≥50% overlap clause.
