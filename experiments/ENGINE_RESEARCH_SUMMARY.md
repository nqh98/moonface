# MoonFace — Engine & Signal Research Program Summary

> **Purpose.** This is a self-contained, AI-readable handoff of the entire MoonFace
> BTC-futures signal-research program (2026-06-08 → 2026-07-07). It is written so a new
> agent can continue the project **without any prior conversation context**. Where a metric
> was never recorded it is written `unknown` — nothing here is invented.
>
> **Read this first.** Each lane below cites a memory slug (the author's private research
> notes, not published) and its `experiments/<dir>/` artifacts, which are the public record.
>
> **Last compiled:** 2026-07-07. **Branch:** `main` (≈143 commits ahead of `origin/main`; most
> research is committed **local-only, unpushed** by user convention).

---

## 0. TL;DR — current state (2026-07-07)

- **The program has a single, exhaustively-replicated negative result** (~55+ closed lanes):
  **positive fixed-horizon price/positioning drift exists on BTC, but no bounded-risk exit or
  governor harvests it within an acceptable drawdown budget.** The "drawdown wall" is
  **structural, signal-independent, timeframe-independent, and survives sizing, portfolios,
  market-neutral hedging, learned models, regime filters, and event-time re-sampling.**
- **No validated, deployable, live edge has ever been found.** Nothing trades live capital.
  The honest production stance is a **WAIT authorizer**.
- **Currently pinned live paper engine:** **Confluence v2.2** (`promotion/engine.json`,
  `enabled: true`, running under `moonface-signal --watch`, emitting `[ENGINE 1h] WAIT`).
  It is a **disciplined heuristic, explicitly "no validated-edge claim."** Its forward verdict
  resolves at the **later of 2027-01-05 or ≥30 completed setups** (one-cycle kill rule).
- **Most recent lane:** `signal-matrix-horizon-harvest` — **CLOSED_NEGATIVE_VALIDATION
  2026-07-07** (Slice-1b clean, well-powered; the "harvest the drift with a governor" thesis is
  **FALSIFIED**). Sealed year **never opened / unspent**.
- **Last-standing curiosities (all paper/underpowered, none deployable):** the MTF counter-trend
  basket (`mtf-lane-results`, "closest-to-deployable ever" but wall-bound + winner's-curse) and a
  handful of frozen forward paper registrations awaiting real forward time.
- **Remaining sanctioned work:** exactly **one** free-data hypothesis left — **H2 `liqprem`**
  (Amihud illiquidity premium) — the terminal item of the final free-data addendum. After that,
  **free data is permanently finished**; only genuinely **new data** (Deribit options chain
  collecting forward; ETF flows blocked) can reopen anything.

---

## 1. Program goal & judging discipline

**Goal (evolved over time):**
1. (2026-06-08) Maximize net R for the MoonFace BTC SMC advisor under a fixed risk gate.
2. (2026-06-12) "Find the most credible source of profitable futures signals" — ranked backlog,
   pre-committed kill criteria, avoid endless exploration.
3. (2026-06-20) Broaden to **practical PAPER-signal candidates** (good enough to emit paper
   signals, forward-validate later) — not only academic edge.
4. (2026-06-22 / 2026-07-03) Build a **real, disciplined paper-signal bot** (Confluence engine),
   judged on **forward paper discipline + honesty**, not on passing DSR.

**Core methodology (constant throughout):**
- **Falsification-first, one hypothesis per cycle.** Pre-register (freeze spec + window + gate)
  **before** any data look. The OOS/sealed tail is a **one-touch lockbox** — opened at most once,
  only if earlier gates pass.
- **Absolute survival required**, not "better than a prior negative."
- **Gate ladder (typical):** gross Stouffer-Z ≥ 2.0 (cost-first pre-screen) → **DSR ≥ 0.95**
  (Deflated Sharpe, lineage-deflated by trial count) → **economic bar** (PF ≥ 1.2, exp ≥ 0.05R,
  MAR ≥ 0.5, MaxDD ≤ 30R @ f=0.01, robust_frac ≥ 0.60) → robustness/plateau/cost-stress.
  Early programs used an **absolute −15R drawdown cap**; later ones a **−30R / ≤30% MC** budget.
- **Kill rules are binding:** a closed lane is **terminal** — no v2, no parameter rescue, no
  re-tune on already-seen data. (The `ap_*` "version-bump the best performer to death" trap is the
  explicit anti-pattern to avoid.)

---

## 2. The single replicated finding (the wall) — DO NOT re-derive

Across **every** family tested — price-derived (SMC, trend, breakout, range-MR, pivots, Donchian,
Bollinger, MTF confluence) and non-price (funding, basis, OI/positioning, taker flow, order-book
depth, aggressor trades, lead-lag, cross-section, macro/exogenous, calendar) — and across
timeframes 15m/30m/1h/2h/4h/1d:

> **Positive fixed-horizon drift exists, but no bounded-risk exit harvests it within the drawdown
> budget.** e.g. `funding_fade` held to a fixed horizon: OOS +1.63R exp / +111R over 68 trades,
> but the unstopped hold draws down −100R to −277R; every stop/bracket/trail that bounds the DD
> either flips the edge negative or still breaches the budget.

This has since been **strengthened** in two directions:
- On several fresh universes there is **no gross OOS drift to begin with** (drift-screen lanes:
  `mechanism_does_not_exist`), which is stronger than "drift exists but is un-harvestable."
- The wall **holds under**: position sizing (`sizing`), portfolios/ensembles (`portfolio`,
  `drift_basket`), market-neutral BTC-hedging (`breadth-neutral`, `mtf neutral`), learned
  non-parametric models (`distributional-path` rung-2 forest), regime filters (ADX, vol-regime,
  macro overlay/selector), event-time re-sampling (`eventtime` dollar bars), and a vol-target +
  drawdown-throttle governor (`signal-matrix`). **None** move the wall.

**Governance corollary (2026-07-07):** the program never dies on *entry selection*; it dies on the
*risk/exit* side. The `signal-matrix` lane put design effort exactly there (separate the forecast
from a portfolio governor) and still closed negative — falsifying the last "we just haven't varied
the right layer" hope.

---

## 3. Conventions, harness & recurring gotchas (operational — read before running anything)

Source: `moonface-workflow-conventions`, `git-staging-incident`, and dozens of per-lane notes.

- **Tests:** `unittest.TestCase` run via pytest; Python 3.11+, **stdlib only** (no numpy in the
  main tree — the `pathsig` forest is the exception and its tests are `--ignore`d). Determinism via
  `random.Random(seed)`.
- **CLIs live at repo-root `tools/`** (not `src/moonface/tools/`). Run study CLIs as
  `.venv/bin/python tools/<x>.py` — **bare `python` is not on PATH.**
- **RTK proxy gaps:** `rtk python …` and `rtk rg …` are **NOT** proxied (fail with "No such
  file"). Use `.venv/bin/python` and plain `grep`/`rg`. `rtk pytest`/`rtk ruff`/`rtk git` **are**
  proxied. **Plans that hardcode `rtk python`/`rtk rg` will fail at runtime.**
- **Git (critical):** **NEVER chain `git add … && git commit`** in one call — a compound command
  once swept 986 untracked cache files into a commit. Stage explicit paths, verify
  `git diff --cached --stat`, then commit separately. **No AI-attribution trailers.** **No
  force-push / history rewrite.** `docs/` (specs + plans) is in the user's global
  `.gitignore_global` → specs/plans are **untracked** and need `git add -f` (repo precedent) if
  they must be kept; otherwise they **do not persist** — the memory files are the durable record.
- **Stale-cache truncation (bit ≥6 lanes):** `fetch_perp_candles` / `fetch_daily_klines` load the
  whole cache file then filter to the requested window; a prior lane's short-window cache silently
  truncates a longer request (3y→2y, 6.5y→1y) with **no error** → false 0-trade / weak results.
  **Always verify prereg bar-counts vs expected; `rm` + refetch if short.** Binance fapi serves
  full history (klines to 2020-01, 15m too). The kline readers were partially fixed with a `.cov`
  coverage-sidecar (commit `37f7b91`); the funding reader got symmetric backward-backfill
  (`4b034a0`); the OI/metrics reader was already safe.
- **`Settings`** is a frozen dataclass; build variants with `dataclasses.replace`.
  `Settings.validate()` only checks LLM retry fields — it does **not** validate trading params.
- **Subagents have no Bash** in this repo's SDD harness → the **controller** runs all
  pytest/ruff/git; implementers only Write/Edit + read-back.
- **Plan-test defects are systemic:** implementation plans repeatedly shipped synthetic test
  fixtures that trip frozen thresholds, are exactly collinear (NW-t=0), or use float `==`. The
  discipline is: **keep implementation byte-verbatim, fix only the fixture, and flag it.** Do not
  bend code to satisfy a bad test.
- **`signal ⊥ research` import boundary** (`tests/test_import_boundaries.py`): `signal/` must not
  import `research/`. Narrow paper-only exceptions are allow-listed in `_PAPER_BRIDGES`
  (playbook, mtf_long). `research → signal` is allowed.
- **LLM:** primary switched to `openai_compatible` / `gpt-5.5` (2026-06-11), omit `temperature`
  for gpt-5*/o-series; **OpenAI key was quota-blocked (HTTP 429)** — research advisor falls back
  to heuristics. Any LLM narrative layer is **veto/permission only, forward-paper only** (LLM
  cutoff = hindsight leakage, so it is not backtestable).

---

## 4. Master lane inventory

Verdict legend: **NEG** = closed negative / mechanism-absent; **KILL** = pre-committed kill rule
fired; **PAPER** = built, paper-only, no deployable line crossed; **BLOCKED** = data/feasibility;
**LIVE** = currently pinned. All are BTC unless noted. "Sealed" = one-touch lockbox status.

| Date | Lane (memory slug) | What | Verdict | Key metric | Sealed |
|---|---|---|---|---|---|
| 06-09 | `phase2-postmortem-verdict` | SMC advisor, gates off | NEG | −1380R, ~28% win, no edge anywhere | n/a |
| 06-09 | `edge-probe-results` | 19 classical-TA entries, H1, ATR bracket | NEG | 0 OOS-valid; breakouts show +horizon drift only | n/a |
| 06-09 | `pivot-confluence-results` | 8 pivot filters | NEG | 2/8 pass *relative* rule (levelbreak), still −OOS | n/a |
| 06-09 | `exit-probe-results` | 30 entry×exit combos, H1 | NEG | 0 clear gate; lone survivor = MC artifact | n/a |
| 06-09 | `edge-probe-h4-results` | 27 signals, H4 | (diag) | donchian_break dominates; 3-entry set derived | n/a |
| 06-09 | `exit-probe-h4-results` | H4 exits | NEG | DD −16R…−153R vs 15R budget | n/a |
| 06-09 | `sizing-results` | H4 fixed-fractional sizing | NEG | all 3 entries unsizable (chosen f=0) | n/a |
| 06-09 | `funding-probe-results` | funding fade/confirm/flip, H4 | NEG | fade/flip +horizon drift, bracket-invalid | n/a |
| 06-10 | `basis-probe-results` | spot-perp basis discount | NEG | 0/4 cells; stopping-condition B | spent(empty) |
| 06-10 | `positioning-exit-probe-results` | exit battery on cleanest-drift entries | NEG | Outcome A; funding_fade fixed_bracket +76.7R but DD-invalid | n/a |
| 06-11 | `signal-core-status` | `moonface-signal` runtime + promote path | (infra) | 304 tests; merged→origin/main `e1f9f0a` | n/a |
| 06-11 | `lead-lag-results` | ETH-leads-BTC, 6 hyps | NEG/KILL | anomaly holdout MAR −0.62; lockbox untouched | untouched |
| 06-11 | `multi-asset-transfer-gate-incident` | ETH/SOL transfer v1 | (void) | lockbox spent on ZERO candidates (error-parked) | uncontaminated |
| 06-11 | `multi-asset-v2-results` | ETH/SOL transfer v2, clean rerun | NEG | best DSR 0.054 vs 0.95 | untouched |
| 06-12 | `positioning-domain-results` | 80 OI/positioning hyps, Vision metrics | NEG | oi_build_momentum DSR 0.30 (strongest-ever) | untouched |
| 06-12 | `positioning-transfer-results` | oi_build on ETH/SOL | NEG/KILL | ETH DSR 0.933 / SOL 0.890 (closest-ever miss) | untouched |
| 06-12 | `xsection-results` | cross-sec mom/carry, 714 perps | NEG/KILL | mom_30 DSR 0.83; sealed tail −91.6% DD (gate calibrated) | spent |
| 06-12 | `oibuild-mechanism-verdict` | pooled OI-build event study, 16 assets | mech-absent | pooled −0.64%/event, sign 8/16; lineage retired | n/a |
| 06-12 | `bookdepth-study-verdict` | order-book imbalance, 16 assets | retired | real at h=1 (+1.25bps) but 10× under cost (net Z −5.2) | n/a |
| 06-12 | `participation-advisor` | WAIT-default policy engine | (infra) | ships `enabled:false`; committed `14e034d` | n/a |
| 06-12 | `reconfirmation-cycle1` | quarterly Donchian reconfirm | DEGRADED | 4h OOS −1.55R; mandate stays disabled | n/a |
| 06-15 | `funding-fade-transfer-results` | the "unpulled lever" under sizing, ETH/SOL | NEG/KILL | both fail stage-2 (neg holdout MAR) | untouched |
| 06-15 | `tunnel-signal-engine-branch` | Pine Tunnel+CHOP port | NEG | real BTC → no_edge (DSR 0.0); branch unmerged | n/a |
| 06-16 | `drift-screen-results` | path-aware drift screen, 16 fresh assets | mech-absent | all 7 signals; floor 0.1319 | n/a |
| 06-16 | `multifamily-drift-screen-results` | funding/OI/orderbook screen | mech-absent | 8/9; funding_confirm inconclusive | n/a |
| 06-17 | `pathsig-rung0-baseline-results` | path-signal rung-0 | (baseline) | DSR 0 on all 30; wall reproduced | 0.2 sealed |
| 06-17 | `distributional-path-program` | learned path-distribution forest (rungs 0-2) | NEG/KILL | rung-2 forest h6 −220.9R / h12 +35.9R DSR 0; framework thesis FALSIFIED | SEALED unopened |
| 06-17 | `bab-results` | betting-against-beta cross-sec L/S | NEG/KILL | in-sample MAR 1.93 → tail MAR −0.94 | spent |
| 06-17 | `resrev-results` | 1-day residual reversal | NEG/KILL | gross Z −0.18 (coin flip), fails pre-screen | spent |
| 06-17 | `liqrev-results` | OI-collapse reversion, pooled | NEG/KILL | +0.229%/event but Stouffer Z 0.92, breadth 9/16 | spent |
| 06-17 | `calseason-results` | calendar/funding-settlement cells | NEG/KILL | best |Z|1.54 vs 3.0 gate; LAST backlog item | spent |
| 06-17 | `newdata-readiness-results` | provider-neutral data-readiness gate | (infra) | dry-run ready (synthetic); real provider human-gated | n/a |
| 06-17 | `aggressor-trades-rung0-build` | aggressor-trades info-test tooling | (infra) | scaffolding only, no edge tested | sealed(unused) |
| 06-18 | `aggressor-trades-freedata-feasibility` | free aggTrades feasibility | re-scope | Q6 NO: frozen feature = monotone transform of failed taker ratio | n/a |
| 06-18 | `deployable-swing-slice1-build` | Donchian swing pipeline (S1/S2) | PAPER | Slice-2 PASS robust 0.79; PF 1.75 exp 0.44R MAR 4.68 | n/a |
| 06-19 | `multistyle-watch-build` | multi-style watch orchestration | (infra) | Swing 4h + empty Day slot; 780 tests | n/a |
| 06-20 | `dual-timeframe-edge-search-results` | 9-cell price search 4h+15m | NEG | all die at stage-1 gross Z<2.0 | never opened |
| 06-20 | `donchian-4h-paper-status` | 4h long-only Donchian trend-follower | PAPER→WITHDRAWN | INCONCLUSIVE; trailing-365d −11.76R; reg **withdrawn 2026-07-03** | n/a |
| 06-20 | `system-search-prereg-frozen` | 72-cell system-level search | NEG | all fail DSR (top 0.401); holdout never opened | never opened |
| 06-21 | `practical-signal-discovery-results` | practical paper-signal lane, 1h+4h | NEG | 0 selection survivors; top DSR 0.226 | never opened |
| 06-21→07-02 | `btc-specialized-lane` | 3-slice BTC-specialized optimization | NEG | all 3 slices fail; edge decays as TF shrinks (95%→47%→20%) | S3 never opened |
| 06-22 | `playbook-signal-engine-results` | MTF trend-playbook engine | NEG | 0/12 clear battery; sealed never opened | never opened |
| 06-24 | `confluence-engine-lane` | v1 stateful confluence paper engine | (infra→v2) | merged local main; ships disabled | n/a |
| 06-25 | `confluence-engine-forward-faithful-results` | honest replay of v1 engine | PAPER | +39R/+71R headlines = ARTIFACTS (fixed `5370d41`); stays WAIT | n/a |
| 06-25 | `portfolio-tournament-results` | 8-ensemble same-data portfolios | NEG | Step-0 corr screen PASS but 0/8 clear DSR | never opened |
| 06-25 | `practical-full-reeval-results` | DSR-free re-eval, ALL 11 price families | NEG | 3/132 clear train battery, ALL reverse in recent sealed | opened(3) |
| 06-26 | `exogenous-lane-results` | FRED macro + Deribit DVOL conditioning | NEG/KILL | Stage-1 survives (t=2.51) → DSR 0.0 + MaxDD −30.14R | not run |
| 06-26 | `regime-overlay-results` | Donchian × FRED macro overlay | NEG | 0/12 beat base in-sample | n/a |
| 06-26 | `regime-selector-results` | macro strategy-selector | NEG | no cell beats always_trend (filter subtracts) | n/a |
| 06-26 | `donchian-adx-filter-results` | ADX entry gate on Donchian | NEG | gate targets wrong trades (high-ADX failures carry loss) | n/a |
| 06-27 | `ls-tournament-results` | 4h Donchian L/S tournament + exit ablation | NEG | survivor reverses in sealed holdout | spent |
| 06-27 | `exit-ablation-results` | 14 exits on the L/S survivor | NEG | 0/14 clear recent bar; failure is entry not atr_trail | n/a |
| 06-27 | `breadth-thrust-results` | top-20 breadth-thrust timing | REOPENED | OOS +sign but n=23 CI [−0.62,+1.12]; frozen fwd reg | forward |
| 06-28 | `breadth-internal-v2-results` | power-honest breadth harness, K=4 | forward | net_new_highs n=66 +0.40R (fails Bonferroni); 2 fwd | n/a |
| 06-28 | `breadth-internal-lanes23-results` | HF block-bootstrap + net-vote ensemble | forward | breadth_momentum +0.154R; ensemble diagnostic-only | forward |
| 06-28 | `breadth-confirm-results` | net_new_highs on disjoint universes | mech-unconf | discovery reproduces exactly; slices wash to ~0 OOS | n/a |
| 06-28 | `breadth-momentum-confirm-results` | breadth_momentum disjoint universes | mech-unconf | both leads fail cure → universe-selection artifacts | n/a |
| 06-28 | `breadth-xasset-confirm-results` | breadth leads → ETH/SOL leg | mech-unconf | sign transfers; confound = time+beta not asset | n/a |
| 06-28 | `breadth-neutral-results` | BTC-hedged market-neutral test | NEG (decisive) | transfer was ENTIRELY crypto beta (β 1.15–1.36) | n/a |
| 06-28 | `drift-basket-results` | beta-neutral vol-target drift basket | NEG | net −0.64, Sharpe −0.05, DSR 0.017; hedge held, wall held | spent |
| 07-01 | `bb-breakout-harvest-results` | bb_breakout drift harvest gate | NEG | all 12 cells die stage-1 (best z 1.725) | n/a |
| 07-01 | `mtf-confluence-results` / `mtf-lane-results` | 15m entry + HTF regime gate (MTF) | PAPER | STRONGEST live signal; 1d-trend+15m-RSI-dip; basket "closest-to-deployable" | forward |
| 07-02 | `donchian-volregime-results` | vol-regime filter on Donchian spine | NEG/KILL | every gate removes the profitable trades | never opened |
| 07-02 | `liqladder-results` | liquidation-ladder magnet (ΔOI) | mech-absent | pooled −0.00064/event, Stouffer −1.90 | n/a |
| 07-03 | `aggtrades-hawkes-results` | Hawkes excitation-asymmetry, aggTrades | KILL | median IC 0.00488, NW-t ≈0; aggressor lane closed | SEALED unopened |
| 07-03 | `macro-event-results` | FOMC/CPI event-window conditioning | NEG/KILL | best p_le0 0.173 vs 0.0125 Bonferroni | spent |
| 07-03 | `deribit-chain-collector` | Deribit options-chain forward collector | LIVE(data) | daily snapshots; readiness ~2027-01; **cron = human ops** | n/a |
| 07-03 | `etf-flow-feasibility` | US spot-ETF daily flows | BLOCKED | access bot-walled at Stage 0 | n/a |
| 07-04 | `confluence-v2-plan` | Confluence v2/v2.1 rebuild | (infra) | two archetype scorebooks, veto-only gate, shadows | n/a |
| 07-04 | `calibration-diagnostic-results` | offline v2 score-calibration | UNCALIBRATED | MEAN_REVERT ρ≈0 dead; TREND weak, Tier-A inverts | n/a(read-only) |
| 07-05 | `scoring-audit-lane` | read-only two-stage scoring audit | (audit) | trend ADEQUATE / revert NO_SIGNAL; m4_pullback HARMFUL | n/a |
| 07-05 | `confluence-v22-prune` | **v2.2 = v2.1 minus m4_pullback** | **LIVE** | sanity replay 130 trades +40.14R PF 1.31 DD −21.71R | forward clock |
| 07-05 | `trend-score-repair-results` | 3 audit-licensed score repairs | NEG/KILL | all fail Gate-1 at α/3; closest c2 Δρ +0.0163 | never opened |
| 07-06 | `freedata-addendum-design` | final 3-hyp free-data addendum | (plan) | H3→H1→H2 terminal stop rule | n/a |
| 07-06 | `advval-results` | adversarial-validation instrument (H3) | KILL | retrodiction ρ −0.18; no harness change | 0 spend |
| 07-06 | `eventtime-results` | dollar-bar vs clock-time twin (H1) | KILL | best improvement 0.2011 vs ≥50% needed | n/a |
| 07-06 | `regime-mechanism-engine-v3` | v3 regime→specialist engine + eval | NEG/not-promoted | Gate-1 fails 3/4; −62.9R @3× cost; deflated CI straddles 0 | SEALED unopened |
| 07-07 | `signal-matrix-horizon-harvest` | forecast + drawdown governor (Slice-1/1b) | **NEG (decisive)** | Slice-1b n=106 CI [−0.86,+0.73] straddles 0; thesis FALSIFIED | SEALED unopened |

*(Also on record but not signal lanes: `autopilot-objective-achieved-artifact` — an autopilot
"objective_achieved" champion was a compounded-MAR artifact with −99.93% holdout DD; no drawdown
gate in the autopilot lockbox. Re-confirms, not overturns, the wall.)*

---

## 5. Lane detail (grouped) — metrics, artifacts, verdicts

### 5.1 Original falsification program (2026-06-08 → 06-10) — `PROGRAM_CONCLUSION.md`

11 cycles on BTC free OHLCV+funding, 3y 4h/1h, one-touch lockbox, **−15R absolute DD cap**.
Diagnostics engine → edge probe → pivot filters → exit probe → H4 edge/exit/sizing → funding →
OI (shelved) → basis (stopping-condition B) → positioning-exit (Outcome A). Verdict: **no robust
absolute OOS edge; drawdown wall structural.** The one lever deliberately **not** pulled:
`funding_fade + fixed_bracket` scored **OOS +76.7R (+1.13R exp)**, rejected only by the −15R cap —
recorded as the sole data-motivated successor (later killed on transfer, §5.3). Artifacts:
`experiments/{diagnostics,edge,exits,funding,basis,positioning_exits,sizing}/`. Reusable engine:
`src/moonface/backtest/edge/` + `src/moonface/backtest/diagnostics/`.

### 5.2 Signal-core infra + first reopening (2026-06-11 → 06-12)

- **Signal-core** merged to `origin/main` (`e1f9f0a`): `moonface-signal` console script, tiered
  ladder (promoted→participation→baseline), torn-write-safe journal, forward gate,
  `tools/promote.py`. Honest `WAIT (no validated strategy)` default. **This is the only work
  pushed to origin** in the early program.
- **ETH/SOL transfer v1/v2, positioning, xsection** all closed negative (§4 table). Key calibration
  proof: `xsection` mom_30 was the gate's only rejected OOS-passer and its **sealed tail showed
  −91.6% DD** — the DSR gate is demonstrably *calibrated*, not merely strict.
- **Mechanism studies:** `oibuild` (16 assets, mechanism absent → OI-build lineage permanently
  retired), `bookdepth` (real at h=1 but 10× under cost → retired). Reusable harness:
  `tools/oibuild_study.py` + `src/moonface/research/oibuild_study.py` (event-study +
  sign-test/Stouffer pooling + tripartite verdict) — **use this to test any future mechanism on
  new data.**
- **`participation-advisor`** (`src/moonface/signal/participation.py`, commit `14e034d`): the
  post-program WAIT-default policy. Ships `enabled:false`; enabling is a human edit. Enforces
  `risk_fraction × 277R ≤ max_account_drawdown` (277R = worst unstopped research DD).

### 5.3 Backlog reboot + cross-sectional reopening (2026-06-12 → 06-17)

`research-backlog-reboot`: ranked backlog in **tracked `experiments/BACKLOG.md`**, two-cycle stop
rule. `funding-fade-transfer` (the "unpulled lever" under MAR/sizing) closed negative on ETH/SOL.
Then the human-authorized reopening: **`bab`, `resrev`, `liqrev`, `calseason`** — all failed their
frozen gates (`PROGRAM_CONCLUSION.md` "2026-06-17 Reopening Closeout"). Both signed cross-sectional
**risk-premium and mean-reversion spaces are falsified** on the 714-perp universe.

### 5.4 Post-handcrafted: learned path-distribution (2026-06-16 → 06-17) — `distributional-path-program`

Thesis: "the limiting factor is the *framework not the data*" — model the forward **path
distribution**, not terminal direction. Built on branch `feat/path-signal-foundations` (unmerged,
kept as-is): foundations + rung-0 (raw) + rung-1 (regime ensemble) + rung-2 (from-scratch numpy
CART distributional forest). **Rung-2 = clean ladder KILL:** h6 −220.9R (worse than rung-1), h12
+35.9R but DSR 0.000 and DD −63.6R (>4× cap). **Framework thesis FALSIFIED on existing data;
lockbox SEALED, never opened.** 653 tests. Only remaining path = new data.

### 5.5 Deployable / practical paper-signal lanes (2026-06-18 → 07-02)

- **Donchian swing pipeline** (`deployable-swing-slice1-build`): the one lane that ever **passed
  its own bar** (Slice-2 PASS, robust 0.79, PF 1.75 / exp 0.44R / MAR 4.68 / maxDD −7.79R) — but
  **paper, not live.** Became the 4h long-only Donchian paper thread (`donchian-4h-paper-status`),
  INCONCLUSIVE (trailing-365d −11.76R, ~18mo chop DD), **registration WITHDRAWN 2026-07-03** by the
  v2-only refocus (config archived under `promotion/archive/2026-07-03-v2-refocus/`).
- **System-search (72 cells), practical-discovery, BTC-specialized (3 slices), playbook engine,
  practical-full re-eval, dual-timeframe search** — **all NEGATIVE.** Recurring shape: drift
  harvests in-sample/validate, then **reverses in the recent sealed window** or is
  **outlier-dependent**; dropping DSR rescued nothing (recency, not DSR, is often the killer). Edge
  decays monotonically as timeframe shrinks (BTC-specialized: 95%→47%→20% net-R-positive).
- **Confluence v1 engine** (`confluence-engine-*`): the `+39R`/`+71.3R` headlines were
  **artifacts** (expanding vol baseline; frozen 2020-22 sample latched by an all-time DD breaker;
  net-negative ex-best-3). Fixed to a faithful rolling-`lookback_bars` replay (`5370d41`, pushed).
  Engine stayed WAIT/paper. This lane became the base for v2.

### 5.6 Breadth-internal family (2026-06-27 → 06-28) — market-INTERNAL info set

New idea: time BTC from the **aggregate breadth of the top-20 USDT-perp universe** (BTC excluded).
Leads: `breadth_thrust`, `net_new_highs`, `breadth_momentum`. Journey: in-sample DSR kill was a
**false negative** (thrust OOS +sign, underpowered); power-honest harness gave 2 forward candidates;
then **three orthogonal perturbations bounded the family:** disjoint-universe = FAIL (selection
artifact), asset-transfer = survives in sign, **market-neutral (BTC-hedged) = the survival was
ENTIRELY crypto beta** (β 1.15–1.36). **Market-neutral breadth family CLOSED.** BTC-directional
`net_new_highs` (n=66, can't hedge BTC vs itself) survives only as an underpowered forward
candidate. Reusable: `src/moonface/research/power_harness.py` (bootstrap + Bonferroni, no
deflation, never gates in-sample).

### 5.7 MTF counter-trend lane (2026-07-01) — `mtf-lane-results` — the strongest live curiosity

1d trend gate decides direction; 15m RSI(14) ≤30 dip / ≥70 rip enters the in-trend side; 2-day
hold. **First and only program signal to survive the "no recent edge" killer** (positive in recent
2y OOS). Headline BTC full 6.5y: n=973, PF ~1.24, +0.58R, MAR 4.53. The **regime-quality × 4-leg
basket** (BTC/ETH/SOL/DOGE, equal weight) is the **"closest-to-deployable result the program has
produced"**: clears 3/5 ECON gates, MAR 5.81, robust_frac up to 1.0, recent PF 1.235 clears — **but
still fails the fixed-f 30R DD cap (sizing) and DSR (0.26–0.51, winner's-curse).** Market-neutral
test proved the alt-leg transfer is **crypto beta**, not alpha; the load-bearing edge is
**BTC-directional long-only dip-buy** (long book PF 1.57 / +1.94R; short book −104R over 2020-23).
Deployed as **signal-only paper bot** `signal/strategies/mtf_long.py` (`_PAPER_BRIDGES`
allow-listed; Telegram + journal, **never places orders**). Forward regs in `experiments/mtf/`.
**Paper only; wall remains the binding constraint. Do NOT re-ask "did you try a stop" (it deepens
DD) or "is the ETH/SOL transfer independent confirmation" (it's beta).**

### 5.8 Confluence v2 → v2.2 (the current pinned engine) (2026-07-03 → 07-05)

User pivot to a **"Pro Trader Assistant"**: ensemble confluence scores + threshold trigger + 1W
macro gating matrix, fixed weights, **no ML**, judged on **forward paper discipline + honesty**,
not DSR.
- **v2 → v2.1 → v2.2** in-place rewrite of `src/moonface/signal/engine/`. Two archetype scorebooks
  (TREND / MEAN_REVERT). Gate is **veto-only at the extreme**; every veto journals a **shadow_score**
  for forward gate-ablation. Weights/thresholds are **frozen constants in code**; any change = new
  `engine_hash` = new registration = fresh clock.
- **Offline calibration diagnostic (read-only): UNCALIBRATED** — MEAN_REVERT book ρ≈0 dead
  everywhere; TREND weak sub-75 ordering (ρ 0.052) but Tier-A (≥75, n=36) inverts.
- **Read-only scoring audit:** trend = CURRENT_WEIGHTS_ADEQUATE, mean_revert = NO_SIGNAL,
  **`m4_pullback` HARMFUL** (removal improves ordering).
- **v2.2 = v2.1 minus `m4_pullback`'s influence** (audit-licensed prune). **LIVE.** Frozen hash
  `b4924f8e…`, sanity replay 130 trades / **+40.14R / PF 1.31 / maxDD −21.71R** / survives 3× cost.
  Watch daemon restarted; journaling at v2.2 hash. **Verdict at the later of 2027-01-05 or ≥30
  setups**, one-cycle kill, success = net R>0 + DD budgets + 4-family ablation report (macro,
  no_ct, long_only, m4_pullback). Registration:
  `experiments/engine/CONFLUENCE_V22_FORWARD_REGISTRATION.md`.
- **`trend-score-repair`** (3 audit-licensed repairs) **CLOSED_NEGATIVE_GATE1** — none beat the
  hand-weighted score OOS at α/3; **sealed window (2025-06-01→end) never opened, still virgin.**

### 5.9 v3 regime-mechanism engine (2026-07-06) — `regime-mechanism-engine-v3`

Deliberate break from additive confluence: `classify_regime → REGIME_MECHANISM matrix picks ONE
specialist (BREAKOUT/PULLBACK/REVERSION) → mechanism trigger is the sole trade decision → score
only sizes.` Core invariant: **score can never create a trade.** Built + diagnostic-replay healthy,
but the registered eval **CLOSED_NEGATIVE_VALIDATION**: Gate-1 fails 3/4 (raw +22.4R but −62.9R @3×
cost; deflated CI [−0.39,+0.59] straddles 0; maxDD −48.4 vs v2.2 −11.6). **Sealed 1yr + ETH/SOL
never opened.** Per spec §11 the negative falls on the **selection architecture itself** — new
knowledge, same wall. **v3 NOT promoted; v2.2 stays pinned.**

### 5.10 Signal-matrix horizon-harvest (2026-07-07) — `signal-matrix-horizon-harvest` — MOST RECENT

First-principles redesign: **separate the signal (a calibrated forecast) from the risk (a portfolio
governor)** and vary the two layers no experiment ever varied — the **exit horizon** and a
**vol-target × drawdown-throttle governor** that de-levers toward a DD budget instead of stopping
out. Two fixed primaries (`momentum_breakout` Donchian, `funding_fade` 48-bar horizon), 6-config
governor grid, EFFECTIVE_TRIALS=12. **Slice-1** hit instrument defects (n collapsed 266→8 from
global-DD throttle state + per-window vs global DD mismatch). **Slice-1b** fixed all three
(per-segment govern reset; retain zero-size trades; recalibrated MIN_VAL_TRADES=40) → **clean,
well-powered CLOSED_NEGATIVE_VALIDATION:** val n=106, net_r −1.82 (−3.08 @3×), **deflated CI
[−0.86, +0.73] tightly straddles 0**, maxDD −22.17. **Decisive: the known drift does NOT survive
the round-trip into a bounded, cost-real, vol-sized strategy → "harvest the drift" thesis
FALSIFIED.** Sealed year **never opened / unspent.** Per stop rule this **CLOSES Slices 2-3.**
Secondary finding: the linear DD-throttle is *reactive* — clustered losses overshoot the budget ~2×
even with per-segment reset ("de-lever toward the cap" ≠ hard-enforce the cap).

---

## 6. Current pinned engine & live paper threads

- **LIVE PINNED:** **Confluence v2.2** — `promotion/engine.json` (`enabled: true`), running under
  `nohup .venv/bin/moonface-signal --watch >> watch.log`. Emits `[ENGINE 1h] WAIT` (currently
  WAIT, conf ~0.15–0.25). Label: **"engine paper — disciplined heuristic, no validated-edge
  claim."** Frozen hash `b4924f8e…`. Verdict at later of 2027-01-05 / ≥30 setups.
- **Signal-only paper bot (separate journal):** `mtf_long` BTC long-only dip-buy
  (`signal/strategies/mtf_long.py`) — Telegram + `journal/mtf_long.jsonl`, **never places orders**,
  reaffirm/downgrade at PF≥1.20 @ n≥40 LONG & ≥6mo.
- **Frozen forward paper registrations awaiting real forward time** (all paper, none live):
  breadth_thrust, net_new_highs, breadth_momentum, breadth ensemble; MTF headline / basket /
  broaden / long-only (`experiments/mtf/`); vol_expansion finalist watch
  (`experiments/practical_full/forward/`). Note the Donchian Slice-3 forward reg was **withdrawn**.
- **Forward data collection (human ops):** Deribit options-chain daily snapshots
  (`experiments/newdata/deribit_chain/chain_BTC.csv`, **git-tracked, do NOT gitignore/clean**);
  readiness gate reachable ~2027-01 **only if the daily cron is run** (it is NOT installed — every
  missed day pushes the gate back).

---

## 7. Sealed-data / lockbox status ledger

**Unspent / uncontaminated sealed tails available for a genuinely-new future hypothesis:**
- `distributional-path` rung-2 lockbox — SEALED, never opened.
- `aggtrades-hawkes` dev/sealed (10,354 buckets) — never opened.
- `regime-mechanism-engine-v3` sealed 1yr BTC + ETH/SOL — never opened.
- `signal-matrix` (Slice-1/1b) sealed year — never opened.
- `trend-score-repair` sealed window 2025-06-01→end — **virgin**, explicitly reserved.
- `multi-asset-transfer` v1 ETH/SOL tail — uncontaminated (v1 was error-parked; v2 spent legitimately).
- `funding-fade-transfer` ETH/SOL tail — stage-2 reject, never spent.
- Various "holdout never opened" search lanes (system-search, practical, playbook, portfolio,
  dual-timeframe, volregime) — sealed slices unopened because 0 survivors reached them.

**Spent tails (do not reuse):** basis (empty), xsection, bab, resrev, liqrev, calseason, drift_basket,
macro_event, ls_tournament, practical-full (3 finalists opened).

---

## 8. What MUST NOT be repeated (hard constraints)

1. **Do not re-tune, "rescue," or v2 any closed lane on already-seen data.** Every kill rule is
   terminal. The `ap_*` version-bump-the-champion trap is the named anti-pattern. A closed
   mechanism does not get a parameter grid, a new exit, a new lookback, or a flipped sign.
2. **Do not reopen the free-data axes.** Price / funding / basis / OI / positioning / taker-flow /
   order-book / aggressor-trades / lead-lag / cross-section (mom, carry, BAB, residual-reversal) /
   calendar / macro-event / exogenous-conditioning are **all falsified or mechanism-absent.** The
   only sanctioned free-data item left is **H2 `liqprem`** (§9).
3. **Do not re-ask the wall's already-answered sub-questions:** sizing doesn't rescue it; portfolios
   don't; market-neutral hedging strips the "edge" to crypto beta; a stop on the MTF cell *deepens*
   DD; learned models re-hit it; dollar-bars don't fix it; a drawdown governor doesn't harvest it.
4. **Do not touch the frozen live engine** (Confluence v2.2 constants/hash) before its horizon; any
   change is v2.3 = new hash = new registration = **fresh clock** (resets the paper record). No
   peeking-to-decide.
5. **Do not modify or resurrect the withdrawn Donchian Slice-3** config without a NEW registration.
6. **Do not misread paper/underpowered curiosities as edges:** the MTF basket "closest-to-deployable"
   is still wall-bound + winner's-curse; breadth leads are crypto beta / universe artifacts; every
   `+NNR` headline in this program has an OOS-reversal or outlier or artifact caveat.
7. **Do not spend a sealed tail** except through a fresh pre-registration whose hypothesis is
   genuinely different (new mechanism or new data), and only when earlier gates pass.
8. **Do not push to origin, force-push, or rewrite history** unless the user explicitly asks; do not
   chain `git add && git commit`; do not add AI-attribution trailers.

---

## 9. Valid next steps (the only sanctioned moves)

1. **H2 `liqprem`** — the terminal free-data hypothesis (`freedata-addendum-design`). Amihud
   illiquidity premium, beta-neutral quintile book, punitive asymmetric costs (5/25 bps),
   min-viability universe floor, cost-first pre-screen. Either branch closing **closes the entire
   cross-sectional space permanently.** Implementation plan **not yet written** — use the
   writing-plans skill. **If it closes negative, free data is permanently finished — no reopening
   under any framing.**
2. **Let the frozen paper clocks run.** Confluence v2.2 (verdict ~2027-01-05), mtf_long, and the
   breadth/MTF/vol_expansion forward registrations resolve only in real forward time. The correct
   action is usually **wait and periodically `--report`**, not new searches.
3. **New-data program (the only structural reopening).** Run the Deribit options-chain collector
   daily until the ~2027-01 readiness gate passes, then pre-register a dealer-gamma hypothesis
   (resolve dealer-sign convention *at* prereg). ETF flows are BLOCKED at access (human A/B/C
   pending). Any real provider must clear `tools/newdata.py assess` (readiness gate) **before** any
   alpha prereg. The aggressor-trades tooling exists but its frozen feature reduces to a failed
   family — a genuinely new **trade-level** feature (large-print imbalance / size-vs-count
   divergence / print-rate) would be required.
4. **Reusable instruments for any new mechanism** (do not rebuild): `oibuild_study` pooled
   event-study harness; `power_harness` (bootstrap + Bonferroni, no deflation); the honest-eval
   toolkit `signal.engine.repair` (segment_panel / block_ci_q / replay_metrics / cost_stress); the
   `newdata` readiness gate; the frozen econ bar / DSR ladder.

---

## 10. Code & artifact map

- **Runtime / live:** `src/moonface/signal/` — `cli.py --watch` daemon, tiered ladder
  (promoted→engine→participation→baseline), `journal/`, `promotion/`. Console script
  `moonface-signal`. Current engine: `src/moonface/signal/engine/` (Confluence v2.2); v3 lives in
  `src/moonface/signal/engine/v3/` (built, not promoted); matrix live primitives in
  `src/moonface/signal/matrix/`.
- **Research:** `src/moonface/research/` (per-lane packages: breadth, breadth_confirm,
  breadth_internal, mtf, xsection, bab, resrev, liqrev, calseason, exogenous, donchian_*, matrix,
  pathsig[unmerged], practical, btcspec, playbook, system_*, portfolio, macro_event, advval,
  eventtime, oibuild_study, drift_screen, power_harness, newdata, participation, reconfirm, …).
- **Backtest core (frozen):** `src/moonface/backtest/` — `engine.py`, `edge/`, `diagnostics/`,
  `trend_sim.py`, `funding.py`, `walkforward.py`, `econ.py`, `universe_data.py`, `metrics_data.py`,
  `bookdepth_data.py`. Foundation: `src/moonface/foundation/` (data, series, indicators, exits,
  metrics).
- **CLIs:** repo-root `tools/*.py` (one per lane).
- **Evidence (tracked):** `experiments/` — `PROGRAM_CONCLUSION.md`, `BACKLOG.md`, `engine/`
  (all registrations + results + audit/calibration/repair/v3/matrix JSON), and per-lane run dirs.
  `experiments/newdata/deribit_chain/` is **git-tracked forward data — never clean it.**
- **Durable narrative:** the memory files (this program's real "lab notebook"), indexed by
  `…/memory/MEMORY.md`. **`docs/` specs/plans are gitignored and largely do not persist** — treat
  memory + `experiments/` as the source of truth.

---

## 11. Test / build status

- Test suite is `unittest`-via-pytest, stdlib-only. **Last recorded green counts** (grow as lanes
  land): signal-matrix Slice-1b freeze **2077 passed**; v3 eval **2057 pass**; trend-score-repair
  **1896 passed / 3 skipped**; v2.2 freeze **1862 passed / 3 skipped**.
- **Known `--ignore` set:** `tests/test_pathsig_{forest,rung2,rung2_cli}.py` (numpy not installed;
  they belong to the unmerged distributional-path branch). Occasionally a `portfolio_search`
  window-constant test failure appears from a stale frozen window — unrelated to current work.
- **Non-hermetic gotcha:** `tests/test_signal_cli.py` fails (9 tests) **iff** a live enabled
  `promotion/engine.json` sits at the default `--engine` path (they don't pass `--engine`). Not a
  regression; the live engine config is intentionally enabled for the forward paper run.
- **Lint:** `ruff check` clean on `src/` + `tools/` (+ tests where noted). Note `line-length=100`
  is set but **E501 is not enforced**; **E402 is not enabled** (redundant `# noqa: E402` appears in
  some plans — omit it).

---

*End of summary. To continue: read the relevant per-lane memory file(s) cited above before acting,
run impact analysis per the repo's GitNexus CLAUDE.md before editing any symbol, and honor every
kill rule and frozen registration.*
