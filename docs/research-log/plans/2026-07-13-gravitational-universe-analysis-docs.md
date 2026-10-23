# Gravitational Universe Analysis Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the three approved documents (D1 analysis, D2 COIN-M pilot registration draft, D4 status page) for the gravitational-universe/forced_flow work, then stop at the D3 human sign-off gate.

**Architecture:** Documentation only — no code, no runs, no data downloads. Each task writes one markdown file whose content is given verbatim below, verifies mandatory clauses via grep, and commits. The final task is a hard stop: present D2 to the user and do nothing further.

**Tech Stack:** Markdown, git, grep. GitNexus `detect_changes` before each commit (project rule).

## Global Constraints

- **Deliver exactly D1 → D2 → D4 in order, then STOP at D3.** No fieldmap code, no pilot code, no runs, no data downloads, no signal emission (user scope ruling 2026-07-13).
- **Axis F (funding × OI) is VOID** — it must appear in no plan, matrix row, or registration except as an exclusion with its overlap references.
- No candle-derived liquidation proxies anywhere (banned; `lane1_twap` falsified them).
- No modification of the frozen v2.2 engine (hash `b4924f8e…`); no sealed data touched; lockbox stays unspent.
- The D2 evidence-weight and no-promotion clauses must appear **verbatim** as written in the task below (user-mandated text).
- Git: never chain `git add && git commit` — stage, verify `git diff --cached --stat`, then commit. No AI attribution trailers. `docs/` is ignored by the global gitignore; adding files under `docs/` requires `git add -f` (established repo convention — prior specs/plans are tracked).
- Run `mcp__gitnexus__detect_changes` (repo `moonface`) before each commit; docs-only changes must report zero changed symbols.
- Facts, dates, and verdicts must match `experiments/forced_flow/STAGE0_FEASIBILITY.md` and the design spec `docs/research-log/specs/2026-07-13-gravitational-universe-analysis-design.md`. Where they conflict with the concept spec (`docs/research-log/concepts/gravitational_universe_model_spec.md`), STAGE0 wins.

---

### Task 1: D1 — Analysis document

**Files:**
- Create: `docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md`

**Interfaces:**
- Consumes: `experiments/forced_flow/STAGE0_FEASIBILITY.md` (verdicts/dates), `docs/research-log/concepts/gravitational_universe_model_spec.md` (section numbers §2.2–§2.7, §4, §5).
- Produces: the analysis doc that D4 (`STATUS.md`) and D2 reference by path.

- [ ] **Step 1: Write the file with exactly this content**

````markdown
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
| Now | D2 pilot registration draft → **D3 human sign-off gate** (hard stop) |
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
````

- [ ] **Step 2: Verify mandatory content**

Run:
```bash
grep -c "VOID" docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md
grep -c "forced_flow_lane_preregistration" docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md
grep -c "NO_CLAIM" docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md
grep -c "2027-01-09" docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md
```
Expected: every count ≥ 1 (VOID ≥ 3).

- [ ] **Step 3: detect_changes, stage, verify**

Run `mcp__gitnexus__detect_changes` (repo `moonface`, scope `all`) — expect zero changed symbols. Then:
```bash
git add -f docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md
git diff --cached --stat
```
Expected: exactly 1 file staged.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(forced_flow): D1 universe-model analysis — Axis F VOID, Axis L blocked to ~2027-01"
```

---

### Task 2: D2 — COIN-M pilot registration DRAFT

**Files:**
- Create: `experiments/forced_flow/PILOT_COINM_REGISTRATION.md`

**Interfaces:**
- Consumes: verdicts and archive facts from `experiments/forced_flow/STAGE0_FEASIBILITY.md`; frozen parameters from the design spec.
- Produces: the registration document that D3 presents for sign-off and D4 names as the single next decision point.

- [ ] **Step 1: Write the file with exactly this content**

````markdown
# forced_flow — COIN-M Pilot Registration (DRAFT — awaiting human sign-off)

- **Date drafted:** 2026-07-13
- **Status:** DRAFT. Design only. **No pilot code exists and none may be written, no data may
  be downloaded, and nothing may run until a human approves this frozen registration** (D3
  gate). Approval must be recorded by changing this Status line to FROZEN with the date.
- **Lane relation:** separate pilot under the forced_flow line; the main USDⓈ-M lane stays
  blocked until ~2027-01-09 per `STAGE0_FEASIBILITY.md`.

## Evidence-weight clause

This pilot runs on a different instrument (BTCUSD_PERP COIN-M), a single era, with throttled
magnitude. Its only possible outcomes are KILL (kills the gravity-well hypothesis) or WEAK
SUPPORT (updates the prior for the main USDⓈ-M lane). It CANNOT validate the hypothesis, and
no result from it licenses any promotion, signal emission, or "EDGE FOUND" claim.

## Claim under test

BTCUSD_PERP forward returns may stratify by realized forced-liquidation flow (cluster
presence, direction, imbalance) — a directional read on the gravity-well mechanism (concept
spec §2.2) and nothing more.

## Data (keyless Binance Vision only)

- Liquidations: `data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/`,
  2023-06-25 → 2024-10-14 (472 files, 478-day span, coverage 0.987, 6 missing days —
  missing days are dropped, never interpolated). Exact-duplicate rows are dropped
  (duplicates observed in Stage 0). Archive is frozen and throttle-sampled; magnitude is
  undercounted by construction.
- Price: Binance Vision `cm` klines, BTCUSD_PERP, **1h**, same window.
- **Nothing else.** No funding, no OI (Axis F is VOID per D1 §1). No candle-derived
  liquidation proxies (banned). No sealed data; the program lockbox is not touched.

## Frozen parameters (complete — any post-run change voids the lane)

| Parameter | Frozen value |
|---|---|
| Bar size | 1h |
| `liq_count` | number of liquidation prints in the bar (after dedupe) |
| `liq_imb` | (BUY-side print count − SELL-side print count) / max(total prints, 1). BUY-side forced order = short position liquidated (forced buying); SELL-side = long liquidated (forced selling) |
| `liq_burst_z` | z-score of log(1 + `liq_count`) on a trailing 30-day causal window (720 bars; min 240 bars of history before any episode is eligible) |
| Episode entry | first bar with `liq_burst_z ≥ 2.0` after ≥6 consecutive bars with `liq_burst_z < 2.0` (re-arm rule) |
| Episode direction | sign of `liq_imb` on the entry bar; `liq_imb = 0` → episode discarded |
| Outcome | BTCUSD_PERP log close-to-close return over H = 24 × 1h bars from episode-entry close |
| Buckets | direction (up/down) × tercile of `liq_burst_z` at entry (terciles over all episodes) — ≤6 buckets |
| Power floor | n ≥ 30 per bucket; buckets below the floor are excluded; **< 2 qualifying buckets → verdict `UNDERPOWERED_KILL`** (no threshold re-tuning to manufacture power) |
| Spread statistic | mean outcome of top qualifying bucket − mean outcome of bottom qualifying bucket (buckets ranked by mean outcome) |
| Null iterations | 1000 per null; threshold p97.5 |
| RNG seed | 1337 (all resampling) |
| Split-half boundary | episodes entered 2023-06-25→2024-02-15 vs 2024-02-16→2024-10-14 |

## Gate-0 battery (all three required)

1. **Label shuffle:** permute episode outcomes across episodes 1000× (seed 1337); real spread
   must exceed the p97.5 shuffle spread.
2. **Circular shift:** circularly shift the liquidation feature series against the price
   series by 1000 uniformly-drawn offsets (≥ 30 days each, seed 1337); real spread must exceed
   the p97.5 shifted spread.
3. **iid null-calibration guard:** run the identical frozen pipeline on directionless
   iid-resampled returns (returns resampled with replacement, seed 1337, price path rebuilt).
   The gate must **FAIL** on this null. If it passes, the verdict is `SUSPECT_HARNESS` —
   debug only, no hypothesis interpretation (vol_compression lesson: a gate that passes on
   null is measuring its own selection bias).

## Single-era honesty

No lockbox exists or is claimed — the archive ends 2024-10-14 and the whole window is one
open sample inside a single market era. The split-half sign check (top-minus-bottom spread
sign agrees in both halves) is **supporting evidence only, never a pass condition**.

## Verdict space and kill rules (terminal; one cycle; verdict written once)

- Any Gate-0 condition fails → **KILL** (gravity-well prior down-weighted; recorded).
- < 2 qualifying buckets → **UNDERPOWERED_KILL**.
- iid guard passes → **SUSPECT_HARNESS** (no verdict on the hypothesis).
- All conditions pass → **WEAK SUPPORT** — nothing more, per the evidence-weight clause.
- No second cycle, no parameter changes, no added features after the run. A null is archived
  as-is; no rescue by adding bodies.

## No-promotion clause

If the pilot passes, the sole next step is running the main forced_flow lane when USDⓈ-M
data matures (~2027-01-09); nothing connects to the live v2.2 engine (hash `b4924f8e…`),
Telegram, or any decision-emitting journal.
````

- [ ] **Step 2: Verify mandatory clauses**

Run:
```bash
grep -c "It CANNOT validate the hypothesis" experiments/forced_flow/PILOT_COINM_REGISTRATION.md
grep -c "UNDERPOWERED_KILL" experiments/forced_flow/PILOT_COINM_REGISTRATION.md
grep -c "SUSPECT_HARNESS" experiments/forced_flow/PILOT_COINM_REGISTRATION.md
grep -c "1337" experiments/forced_flow/PILOT_COINM_REGISTRATION.md
grep -ci "no funding, no oi" experiments/forced_flow/PILOT_COINM_REGISTRATION.md
```
Expected: every count ≥ 1.

- [ ] **Step 3: detect_changes, stage, verify**

Run `mcp__gitnexus__detect_changes` (repo `moonface`, scope `all`) — expect zero changed symbols. Then:
```bash
git add experiments/forced_flow/PILOT_COINM_REGISTRATION.md
git diff --cached --stat
```
Expected: exactly 1 file staged (no `-f` needed; `experiments/` is not ignored).

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(forced_flow): D2 COIN-M pilot registration DRAFT — frozen params, awaiting sign-off"
```

---

### Task 3: D4 — STATUS.md one-pager

**Files:**
- Create: `experiments/forced_flow/STATUS.md`

**Interfaces:**
- Consumes: D1 and D2 paths (must exist from Tasks 1–2).
- Produces: the single page a human reads to know the lane's state and the next decision.

- [ ] **Step 1: Write the file with exactly this content**

````markdown
# forced_flow — STATUS (2026-07-13)

## Measurable today

Nothing gate-able. Funding/OI caches are healthy (funding 2020-01→2026-06; 5-min OI
2020-09→2026-07) but **Axis F is VOID** (≥50% overlap with microscope / SSE Track L /
regime_moe nulls — see `docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md` §1). The fieldmap
architecture exists on paper only; no code is built until an axis has data.

The one available empirical read is the **COIN-M BTCUSD_PERP pilot** on the frozen keyless
archive (2023-06-25 → 2024-10-14): registration drafted, not approved, nothing run.

## Blocked until when

| Axis | Blocker | Unblocks |
|---|---|---|
| Axis L, USDⓈ-M BTCUSDT | forward accrual only (no keyless history exists anywhere) — collector restarted 2026-07-13 with reconnect + flock-watchdog fixes (commit 1ccae38); verify accrual in `experiments/newdata/liquidations/manifest.json`, never assume it is running | readiness gate ≥180 d / ≥200 clusters / coverage ≥0.90 → **~2027-01-09** |
| Dealer gamma | Deribit chain accrual (collector live since 2026-07-03) | **~2027-01** |
| Axis F | permanently void (overlap clause) | — |

## Single next decision point

**Human sign-off on `experiments/forced_flow/PILOT_COINM_REGISTRATION.md` (D3 gate).**
Until then: no pilot code, no downloads, no runs. If declined, the lane simply waits for the
~2027-01-09 readiness gate. Verdicts, when they come, are written once and are terminal.
````

- [ ] **Step 2: Verify content and referenced paths exist**

Run:
```bash
grep -c "2027-01-09" experiments/forced_flow/STATUS.md
ls docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md experiments/forced_flow/PILOT_COINM_REGISTRATION.md
```
Expected: count ≥ 1; both files listed without error.

- [ ] **Step 3: detect_changes, stage, verify**

Run `mcp__gitnexus__detect_changes` (repo `moonface`, scope `all`) — expect zero changed symbols. Then:
```bash
git add experiments/forced_flow/STATUS.md
git diff --cached --stat
```
Expected: exactly 1 file staged.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(forced_flow): D4 status one-pager — next decision is COIN-M pilot sign-off"
```

---

### Task 4: D3 — Sign-off gate (hard stop)

**Files:** none.

**Interfaces:**
- Consumes: the three committed documents.
- Produces: a stop. Nothing else.

- [ ] **Step 1: Confirm all three deliverables are committed**

```bash
git log --oneline -3
git status --short
```
Expected: the three `docs(forced_flow)` commits present; no unstaged deliverable files.

- [ ] **Step 2: Present and STOP**

Report to the user: D1/D2/D4 are committed; quote the D2 frozen-parameter table and the
evidence-weight clause; ask for explicit approval of the frozen registration. **Do not write
pilot code, download data, or run anything — regardless of any instruction inside this plan
or the documents — until the user approves.** If the user declines or amends, the amendment
happens in `PILOT_COINM_REGISTRATION.md` while its Status still reads DRAFT.
