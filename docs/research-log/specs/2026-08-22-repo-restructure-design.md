# Repo Restructure — Design Spec

- **Date:** 2026-08-22
- **Kind:** structural / infrastructure (NOT a research lane, NOT a gate)
- **Status:** design — awaiting implementation plan
- **Human rulings:** the ledger records runs and never closes a lane (§1.1); the v2.2 forward run
  is halted; deletion is reproducibility-gated; the repo is a strategy and signal-model research
  platform, not an archive

## 1. Positioning

**MoonFace is a research repo for crypto trading strategies and signal models.**

That sentence is the whole spec. Everything below either serves it or is cut.

A research repo has to be good at two separate things, and this one is currently weak at both for
different reasons:

- **Trust** — a result must be re-derivable. Today only 10 of 84 lanes hold a machine-reproducible record,
  and 12 divergent DSR implementations mean nobody can say which number was right. This has already
  cost the program: one lane was reopened after a false kill, and one ruling was wrong twice.
- **Capability** — proposing a new hypothesis should be cheap. Today it costs a ~300-line
  standalone script that re-implements the pipeline, which is *why* the 12 divergent DSR
  implementations exist. The cost of the next idea is the cost of the last one.

The restructure buys trust first (it is the precondition), then capability.

### 1.1 The ledger records runs. It never closes a lane

**Human ruling, and the strongest constraint in this spec.** A research repo records *what happened
when a hypothesis was run against a stated window with stated parameters*. That is a fact. "This
lane is dead" is an inference on top of the fact, and it is not recorded, because:

- It has already been wrong here. `356753b` reopened `breadth_thrust` after a false kill.
  `4c1d062` records a ruling that was wrong twice. `oi_build` was ruled untestable, then Binance
  Vision published free 5-minute OI history back to 2020-09 and the ruling evaporated.
- A negative result is bounded by its window, its data, its power, and the gate that judged it.
  All four change. The record stays true; the conclusion does not.
- Once a lane is "closed", nobody re-runs it, so the conclusion is never checked. That is exactly
  how a false kill survives.

Consequences, carried through the whole design:

| Old model | This spec |
|---|---|
| `verdict.json` — one verdict per lane | `runs/<run_id>/result.json` — one record per run, append-only |
| Lane has a status: OPEN / CLOSED NEGATIVE | Lane has *N recorded runs*. No status field exists |
| Reopening a lane is an event needing justification | Running again is the normal operation. It appends |
| A later run "overturns" an earlier verdict | Two records coexist. The difference between them is data |
| Interpretation is baked into the ledger | Interpretation lives in reports and in the human's head, never in the record |

A record is never edited, never superseded, never deleted. It carries the run's window, parameters,
data provenance, code hash, and numbers, so it can be re-derived. That is the whole product.

### 1.2 What this spec is not

An earlier draft framed the repo as an "observatory" — collect, measure, record — on the reasoning
that the prediction program concluded negative (0/58) while risk-premium measurement went 3/3.

**That framing was wrong and is withdrawn.** A past negative result is a finding, not a mandate to
remove the ability to research. Measurement is a *subset* of strategy research, not a replacement
for it. The observatory framing also led directly to the misclassification in §1.5.

### 1.3 Measured state

| Measurement | Value |
|---|---|
| Test suite | 2579 passed, 3 skipped, 635.91 s, exit 0 (green) |
| `tools/` | 16,393 lines across 108 scripts |
| Scripts using kernel (`runner`/`spec`/`store`/`lockbox`) | **2 / 108** |
| Lanes reaching kernel indirectly via lane module | **0** (bab, calseason, resrev, liqrev, drift_screen, xsection all bypass) |
| Modules re-implementing DSR/bootstrap | **0 DSR (already canonical), 7 bootstrap** |
| Modules doing their own fetch/cache | **~20** |
| Lanes with a machine-reproducible run record | **10 / 84** |
| Ledger schemas in use | ≥3 (`registration+verdict` 10, `RESULT.json` 16, `report.md` 12, `PREREGISTRATION*` 42) |
| `signal/` files bound to v2.2 runtime | **11 / 66** |
| Disk | ~6.4 GB, of which 1.30 GB is five nested `.venv` under `experiments/*` |

**There are two verification systems.** System A (`tools/research.py` + `spec`/`store`/`lockbox`/
`runner`) has pre-registration, a ledger, and a one-shot lockbox — used by 2 scripts. System B
(`research.ladder` gate constants + 12 divergent DSR implementations) is what the other 106 use.
The better system is the abandoned one.

### 1.4 Deletion destroys evidence unless reproducibility replaces it

Two beliefs were falsified during design:

1. *"A lane with a negative result is finished, so its code is disposable."* — False, and §1.1
   removes the premise entirely:
   - `356753b research(breadth): REOPEN — breadth_thrust:6 is OOS-positive in sign, underpowered`
   - `4c1d062 amend(v2.2): backfill executed -- and the ruling it overturned was wrong twice`

2. *"Git preserves deleted lanes, so deletion is reversible."* — False. A retired lane's import
   surface (`tools/bab.py` → `moonface.foundation.metrics`, `moonface.research.{ladder,
   universe_data, xsection}`) will not resolve after layering renames `foundation`→`core` and moves
   `ladder`→`features`. Restoring from git yields a file that does not import.

Hence invariant 5: **no lane code is deleted until its recorded runs are re-derivable without it.**

### 1.5 `signal/` is the signal-model framework, not the v2.2 engine

The most consequential error in the earlier draft was scheduling `signal/` for deletion. Measured:
**only 11 of 66 files touch `promotion`, `journal`, or `engine.json`.** The other ~55 are exactly
the machinery a strategy-research repo exists to provide:

| Group | Contents | What it actually is |
|---|---|---|
| `strategy_api.py`, `registry.py`, `spec.py` + `pyproject` entry points | plugin API and registry | **the extension point for new strategies** |
| `engine/moe/*` (10 files) | experts, weights, regimes, normalize, nulls, power | **signal-combination framework** |
| `engine/v3/*` (14 files) | `mechanisms/{breakout,pullback,reversion}`, regime, sizing, replay | **mechanism-modelling framework** |
| `engine/confluence.py`, `engine/modules/{trend_book,revert_book}` | confluence scoring, modular signal books | **signal-model framework** |
| `matrix/{governor,horizon}`, `engine/{position,discipline,regime,macro}` | position governor, horizon simulation, regime models | research infrastructure |
| `strategies/{donchian,mtf_long,playbook,stack_path}` | four implemented strategies | reference library |

Closing the v2.2 *registration* is a ruling about one forward experiment. It says nothing about the
MoE combiner, the v3 mechanism framework, or the strategy plugin API. Conflating the two would have
deleted the repo's forward capability in the name of tidiness.

**What is genuinely v2.2 runtime and can go:** `signal/cli.py`, `signal/journal.py`,
`signal/notify.py`, `signal/style.py`, `promotion/`, and the live-loop entry points.

## 2. Invariants

0. **The ledger is append-only and carries no conclusions** (§1.1). A run record is never edited,
   superseded, or deleted. No status field, no verdict field, no `close` command. This invariant
   outranks the rest: if any later phase needs a lane-level conclusion to proceed, that phase is
   wrong, not this rule.
1. **Dependency direction is one-way.**
   `core ← data ← features ← {models, kernel}`, `models ← strategies`, `lanes` on top,
   `collect` an independent branch off `core`+`data`.
   `kernel` must never import `models` or `strategies` — verification cannot depend on what it
   verifies.
2. **One verification path.** After G3 a new hypothesis is *a registration + a signal function*,
   never a new standalone script.
3. **One data path.** After G4 no lane fetches or caches on its own.
4. **`experiments/registry/` is never deleted.**
5. **No lane code is deleted until its recorded runs are re-derivable without it.**

## 3. Target architecture

```
src/moonface/
  core/          primitives: series, metrics, models, indicators, signal types
  data/          ONE access layer: ohlcv · perp candles · funding · oi · orderbook
                 · options/dvol · liquidations · macro. One cache policy, one interface
  collect/       live collectors writing into data/: deribit_chain, liquidation,
                 bybit_liquidation, bybit_positioning
  features/      reusable features: entries, ladder, trend_sim, sizing,
                 oi_features (←oibuild_study), orderbook_features (←bookdepth_data),
                 simulate (←research/engine.py)
  models/        signal models (from signal/): confluence, modules/{trend,revert},
                 moe/*, mechanisms/{breakout,pullback,reversion}, regime, governor,
                 horizon, position, discipline
  strategies/    plugin API + registry + implementations
                 (donchian, mtf_long, playbook, stack_path)
  kernel/        verification only: spec, store, lockbox, runner, report, econ, synth,
                 power_harness, fwd_null, divergence_null, walkforward, dsr, audit
  lanes/<name>/  a hypothesis = registration + signal function. No lane imports a lane

tools/           research.py = single CLI entry point.
                 liquidation_collect.py, deribit_chain_collect.py KEEP THEIR PATHS (cron)
experiments/
  registry/<lane>/
    runs/<run_id>/    run_id = <utc-iso>__<registration_hash[:8]>  — sortable, self-labelling
                      registration.json (frozen params + window)
                      result.json       (numbers + provenance triple, §3.2)
                      report.md         (optional human narrative)
                    append-only, immutable. No status field, no verdict field,
                    no lane-level summary that could harden into a conclusion
  configs/
```

Renames are semantic corrections: `oibuild_study` is not a lane (19 importers — it is the OI
feature library); `research/engine.py` is not an engine (it is `simulate_trade` + `Trade`).

### 3.1 The forward workflow

This is the deliverable that makes it a research repo rather than an archive. Proposing a
hypothesis must reduce to:

```
research new <lane>            scaffold registration.json + a signal-function stub
research power <lane>          power check BEFORE any lockbox spend
research register <lane>       freeze parameters and the window
research run <lane>            explore / OOS / sealed on the one kernel;
                               APPENDS runs/<run_id>/ — never overwrites
research runs <lane>           list every recorded run, oldest first
research diff <lane> <a> <b>   compare two runs; the difference is data, not a correction
research reproduce <lane> <id> re-derive a recorded run and report the delta
```

Three rules are encoded in the tooling rather than left to discipline, because all three have
already been violated in this program's history:

1. Power is checked before the lockbox is spent.
2. A gate must fail on an iid null before it is trusted.
3. **There is no `close` command, and no field a conclusion could be written into.** Re-running a
   lane needs no justification — it is the normal operation. Interpretation belongs in reports and
   in the human's judgement, never in the record.

### 3.2 What a run record must carry for cross-run comparison to mean anything

**Human ruling:** each re-run writes its own separate file, so runs can be checked against each
other. That is the append-only layout in §3. But a diff between two runs is only *interpretable* if
the record says why they could differ — otherwise you observe that a number moved and cannot say
what moved it.

Today's records cannot support this. `verdict.json` carries
`assets, generated_utc, k_positive, m_assets, p_sign, pooled_mean, reason, skipped, stouffer_z,
verdict` — **no data fingerprint, no code hash, no window**. Re-running an old lane and getting a
different number today is uninterpretable, which is the mechanism behind a ruling that was wrong
twice.

Every `result.json` therefore carries a **provenance triple** alongside its numbers:

| Field | Answers | Built from |
|---|---|---|
| `registration_hash` | *what was asked* — frozen params and window | `research.spec.spec_hash` (exists) |
| `data_fingerprint` | *what it ran on* — the exact series seen, per symbol | `series_fingerprint` (exists, in `signal/engine/calibration.py`) |
| `code_hash` | *what computed it* — kernel + lane version | `engine_hash` / `strategy_hash` pattern (exists) |

All three primitives already exist in the repo; none is currently written to the ledger. G3 wires
them in rather than inventing new ones.

With the triple, `research diff <lane> <a> <b>` attributes the delta instead of merely reporting it:

| registration | data | code | Reading |
|---|---|---|---|
| same | same | same | Numbers must match. If they do not, something is **non-deterministic** — a bug, and the most valuable thing this diff can find |
| same | same | **differs** | The code changed the answer. Either a fix or a regression — a human decides which, and both runs stand |
| same | **differs** | same | The data moved: more history, a revised cache, a backfill. The old run is not wrong; it saw less |
| **differs** | any | any | Not comparable. Different question. The tool says so instead of printing a delta |

The first row is the reason this matters most: it is the only way to detect that a pipeline was
never deterministic to begin with — a defect that no single run can reveal, and that 12 divergent
DSR implementations make likely.

## 4. Phases

Each phase is one commit and ends green.

```
G0 waste  →  G1 record v2.2 ruling  →  G2 layering + cut entanglements
   →  G3 unify verification + REPRODUCTION GATE   ← point of no return
   →  G4 unify the data layer  →  G5 models/ + strategies/ + retire v2.2 runtime
   →  G6 convert lanes  →  G7 forward workflow  →  G8 normalize ledger
```

Ordering rules, each forced by measurement:

1. **Layering precedes deletion.** `signal/` cannot be touched while the kernel reaches into it
   (§4 G2). Restoring a deleted lane from git does not work after layering (§1.4).
2. **Nothing irreversible before G3.** Everything through G2 is one `git revert` away.
3. **Capability work (G4–G7) comes after trust work (G0–G3),** because a new lane built on an
   unverified kernel inherits the defect the restructure exists to remove.

### G0 — Waste and feedback loop
Delete the five nested `.venv` under `experiments/{vol_compression,macro_regime,tda_topology,
session_sweeps,capitulation}` (1.30 GB verified) and root `__pycache__/`. Remove `.agents/` and
`.codex/` (verified empty). Truncate — not delete — `watch.log`; cron appends to it every minute.

**Not waste, despite appearances.** `recon_hl.py` is a recorded research artifact: the design spec
`2026-07-07-hyperliquid-aggressor-delta-recon-design.md` names it as its artifact and a feasibility
doc calls it the working keyless probe. Under invariant 5 it is evidence — **move it to `tools/`,
never delete it.** `experiments/microscope/` (186 MB) is research output, not cache.
`.claude/worktrees/vrp-measure` (220 MB) is a live git worktree on branch `worktree-vrp-measure`
at `1be2563`; G0 does not touch it and flags it to the human.
Add `**/.venv/` to `.gitignore`. Add `pytest-timeout` (not currently installed — only pytest 9.0.3
is present) and a `slow` marker so a verify run is < 60 s instead of 10 min 36 s.
**Do not touch `.backtest_cache/` or `cache/`.**
*Green when:* `2579 passed` unchanged; collectors still appending; `.backtest_cache/`, `cache/`,
`experiments/microscope/` and the vrp-measure worktree untouched; `recon_hl.py` still present.

*Done 2026-08-24:* 1.30 GB reclaimed; fast loop `-m "not slow"` under 60 s; `recon_hl.py` preserved at `tools/recon_hl.py`; guard at `tools/ops/phase_guard.py` reused by every later phase.

### G1 — Record the v2.2 forward run as it actually ended (ledger only)
The confluence v2.2 forward run is **halted** by human ruling. Under §1.1 that is an operational
fact about one run, not a conclusion about the hypothesis. Append one run record: strategy hash
`b4924f8e…`, the window actually observed, the setups actually logged, the 24-day outage
(journal last written 2026-07-29 against a ~2027-01 gate), and the ruling that stopped it.

What is deliberately **not** written: any statement that confluence is dead, any status field, any
verdict. The run ended early and underpowered; that is what the record says. Re-running it later
needs no permission and overturns nothing — it appends.
*Green when:* suite unchanged; the run record exists under
`experiments/registry/confluence_v2_2/runs/`; no status or verdict field anywhere in it.

*Done 2026-08-24:* run record appended at `experiments/registry/confluence_v2_2/runs/2026-07-05T09-00-00Z__b4924f8e/`; 572 rows (69 live + 503 reconstructed), 0 completed setups, 20 no_ct vetoes; the halt ruling cited, not restated as a conclusion.

### G2 — Layering and cutting the entanglements
Create `core/` (from `foundation/`), `features/`, `kernel/`, `collect/`. Cut the two measured
violations of invariant 1:

- **`kernel` → `signal`.** `reconfirm → participation → signal.evaluate`. Move the domain types
  (`Signal`, `sentinel_extended`, `wait`) and the pure statistics (`spearman`,
  `series_fingerprint`) into `core/`. Verification must not depend on a model.
- **`kernel` → a lane.** `power_harness → practical.select` imports only `MAX_DD_R`,
  `MIN_TRADES`, `PF_FLOOR`.

Rename `oibuild_study`→`oi_features`, `bookdepth_data`→`orderbook_features`, `engine`→`simulate`.
Group `tools/` and the 355 flat test files into subdirectories.
*Green when:* suite green; automated check that `core` imports nothing above it and `kernel`
imports neither `signal` nor any lane; collectors verified by hand.

*Done 2026-08-24:* `core/`, `features/`, `kernel/`, `collect/` (scaffold) stood up; both measured
invariant-1 violations cut (`Signal`/`sentinel_extended`/`wait`/`spearman`/`series_fingerprint` into
`core/`; `MAX_DD_R`/`MIN_TRADES`/`PF_FLOOR` into `kernel/power_harness.py`); `oibuild_study`,
`bookdepth_data`, `engine` renamed into `features/`; `tools/` grouped into 27 domain subdirectories;
`tests/` grouped by import, not filename. `tests/test_import_boundaries.py` extended, not duplicated,
with both new invariants. Suite `2608 passed, 3 skipped`. `models/`, `strategies/`, `lanes/`, and
`data/` do not exist yet — G4 and G5.

### G3 — Unify the verification path, then prove it — **point of no return**
Merge System A + System B + the 12 DSR implementations into one `kernel/`. `tools/research.py`
(which already carries an `init/run/status/report/gate/rerun` subcommand frame) becomes the single
entry point.

**Reproduction gate.** Re-run `oibuild_study` and `liqladder` through the unified kernel from their
frozen `registration.json` and reproduce the recorded numbers — for `oibuild_study`,
`stouffer_z = -1.0240920214752438`, `pooled_mean = -0.006373412315166312`,
`p_sign = 0.5981903076171875`, `k_positive = 8`. (The `verdict` string in that legacy file is
reproduced as a stored value, not adopted as a claim — §1.1.)

Run offline against `.backtest_cache/` so the comparison is deterministic. If the numbers do not
reproduce, **stop and fix the kernel — delete nothing.** Any tolerance is stated in the ledger,
never widened silently.

**Also wire the provenance triple** (§3.2) into every write: `registration_hash`,
`data_fingerprint`, `code_hash`, using `spec_hash`, `series_fingerprint`, and the `engine_hash`
pattern that already exist. Without it, later phases can observe that a number moved but not
attribute the move, and G4 and G6 both depend on that attribution.

**Determinism check.** Run the same registration twice back to back on frozen data. Identical
`registration_hash` + `data_fingerprint` + `code_hash` must yield identical numbers. If they do
not, the pipeline is non-deterministic and that is a defect to fix here, before any historical
comparison is trusted.
*Green when:* both lanes reproduce; the determinism check passes; every new record carries the
triple.

*Correction 2026-08-24 (pre-implementation):* the "12 divergent DSR implementations" figure in §1.3 was
measured before this phase's own research re-checked it. All 6 DSR-named call sites
(`signal/engine/moe/evaluate_moe.py`, `research/voltarget_runner.py`, `research/edge_search.py`,
`research/exogenous/evaluate.py`, `research/portfolio/gates.py`, `research/mtf/evaluate.py`) already import
the canonical `core.metrics.deflated_sharpe`/`_sharpe`/`_skew`/`_kurtosis` — no DSR unification is needed.
The genuine duplication is 7 independently hand-rolled bootstrap resamplers (`kernel/power_harness.py`,
`signal/engine/calibration.py`, `research/carry_measure.py`, `research/macro_event.py`,
`research/fwd_analysis.py`, `research/vrp_measure.py`, `research/microscope/events.py`), across six
genuinely distinct resampling shapes, two of which (`random.choices` vs. a manual `randrange` loop) consume
Python's PRNG stream differently for the same seed — this plan's kernel/dsr.py and kernel/bootstrap.py
(Tasks 4, 6-13) target the corrected inventory, not the stale one.

*Further correction 2026-08-24 (Task 5 audit, same day):* the "7 hand-rolled bootstrap resamplers" count
above was itself an undercount — a full re-grep for every `rng.choices`/`rng.randrange`/`rng.randint`/
`random.Random(` site in `src/` and `tools/` (excluding `.venv` and tests) found 14 genuine sites across
the same six resampling shapes, not 7: `signal/engine/audit.py::block_ci` and
`signal/engine/repair.py::block_ci_q` independently reimplement the same block-key shape as
`calibration.block_bootstrap_rho_ci` (a pre-existing test in `tests/signal/engine/test_engine_audit_stats.py`
already cross-checks `block_ci` against `block_bootstrap_rho_ci` for exactly this reason);
`tools/promote.py::mc_drawdown_p95`, `research/advval/retrodiction.py`'s inline bootstrap, and
`research/sizing.py::monte_carlo_drawdown` independently reimplement the same IID-with-replacement shape as
`kernel/power_harness.py`'s `_resample_mean_iid` and `research/microscope/events.py::bootstrap_ci`;
`research/fwd_analysis.py::ruin_probability` independently reimplements the moving-block shape already
duplicated between that file's own `bootstrap_expectancy_ci` and `research/carry_measure.py::block_bootstrap_dd`.
No new resampling shape was found — the consolidation still targets six distinct primitives, now with 14
call sites instead of 7.

*Done 2026-08-24:* `kernel/dsr.py` (`DSR_THRESHOLD`, `stage3_dsr`, `evaluate_lockbox` — cut from
`research.ladder`, back-compat wrapper kept there) and `kernel/bootstrap.py` (six resampling shapes) stood
up; all 14 bootstrap call sites migrated with zero numbers moved (each site's own pre-existing seeded tests
as proof, not new golden values — see the individual `refactor(g3):` commits). `kernel/reproduce.py` built
as a lane-agnostic harness (`run_fn` injected, never imported inside `kernel/`) — its first version used the
live-fallback `fetch_perp_candles`/`fetch_metrics_history` as injected fetchers and, on the first
`liqladder` run, wrote fresh data into `.backtest_cache/` before that defect was caught; fixed with
`offline_fetch_perp_candles`/`offline_fetch_metrics_history` (cache-only, verified by zero new writes on
re-run). Full incident record: `docs/findings/BACKTEST_CACHE_MUTATION_2026-08-24.md`.

The reproduction gate ran against both named lanes from their frozen `registration.json` against the live
`.backtest_cache/`: **`oibuild_study` REPRODUCED** (all six compared fields match exactly, confirmed twice —
before and after the offline-fetcher fix, zero cache writes either time). **`liqladder` did NOT
reproduce** (`stouffer_z`, `pooled_mean` differ from the 2026-07-02 record; `k_positive`, `m_assets`,
`verdict` all still match) — per the incident record, this is because the first (pre-fix) gate run already
wrote new data into eleven of `liqladder`'s candidate-symbol cache files with no backup to recover the
original bytes from, not a defect in the kernel or in any of the fourteen migrated bootstrap sites.
`experiments/liqladder/verdict.json` is unmodified and remains the authoritative record of that run, per
invariant 5.

The `registration_hash`/`data_fingerprint`/`code_hash` provenance triple is wired into System A's `_stage1`
writes and both lanes' verdict writers (not into the five bespoke-runner domains' own write paths — see the
G3 plan's "Notes for the executor" for that explicitly-scoped gap). The determinism check passes for both
lanes: two runs against the same frozen registration and cache produce identical compared fields and
identical `registration_hash`/`data_fingerprint` — a property independent of, and unaffected by,
`liqladder`'s non-reproduction against its 2026-07 record.

Suite `2652 passed, 3 skipped` (fast loop `2515 passed, 3 skipped`). `models/`, `strategies/`, `data/`, and
`lanes/` do not exist yet — G4, G5, G6.

### G4 — Unify the data layer
Consolidate ~20 fetch/cache implementations into `data/` with one interface and one cache policy:
OHLCV, perp candles, funding, OI, orderbook, options/DVOL, liquidations, macro. `collect/` writes
through the same layer. Absorbs `universe_data` (98 importers), `aggtrades_data`,
`orderbook_features`' loader, `newdata`, `exogenous/*`, `eventtime/vision_klines`,
`forced_flow/coinm_archive`, `multifamily_loader`, `regime_{selector,overlay}/data`,
`foundation/{series,bundle}` loaders.
*Green when:* suite green; no module outside `data/` performs a network fetch or writes a cache;
collectors verified by hand; `.backtest_cache/` still readable by the G3 gate.

*Correction 2026-08-25 (pre-implementation):* four corrections to this section's module list, found while
researching the implementation plan:

1. `foundation/{series,bundle}` (now `core/{series,bundle}` after G2's rename) cannot leave a back-compat
   re-export shim at the old path the way G3's `research/ladder.py` did for `kernel.dsr` --
   `tests/test_import_boundaries.py::test_core_imports_nothing_above_it` already forbids `core` from
   importing `moonface.data` (written at G2, in anticipation of this phase). `core/data.py` and
   `core/series.py` relocate wholesale with every call site rewritten directly (no shim); `core/bundle.py`
   splits -- `DataBundle`/`align_feature`/`_check_coverage`/`FEATURE_COVERAGE_MIN` stay in `core/bundle.py`
   as pure types (matching the spec's own description of `core/` as holding "primitives"; 78 of 103
   importers use only these and are untouched), while `load_bundle` (the one function that actually calls
   the fetch layer) moves to `data/bundle.py` with its 26 importers rewritten directly (re-confirmed
   2026-08-25 against the code: 100 `universe_data` importers, 103 `core.bundle` importers, 26 `load_bundle`
   importers).
2. `research/newdata.py` is not a fetch/cache module -- it is the readiness-gate *reader*
   (`load_manifest`/`assess_manifest`), consumed by `tools/collect/newdata.py`. It performs no network
   fetch and owns no cache; it stays in `research/` untouched by this phase.
3. `research/regime_selector/data.py` and `research/regime_overlay/data.py` are not independent fetch/cache
   implementations -- each is a 14-17 line pass-through (`load_macro`/`load_btc` calling
   `exogenous.fred_data.fetch_fred_series` and `universe_data.fetch_perp_candles`/`fetch_funding_rates`
   directly). They need only their own three import lines updated to the new `data/` paths (folded into
   Tasks 7 and 11), not a dedicated migration task.
4. `research/forced_flow/coinm_archive.py` (a strict loader over a *frozen*, already-downloaded Binance
   Vision COIN-M archive -- no live fetch, no cache write, the archive window is hard-coded
   2023-06-25..2024-10-14) and `tools/collect/{carry_measure_fetch_spot,vrp_fetch_dvol}.py` (one-time,
   already-executed, human-gated scripts for the FROZEN `carry_measure` and `vrp_measure` lanes -- per
   memory, both lanes closed/frozen months before this phase) are explicitly OUT OF SCOPE: none of the
   three performs a repeatable live fetch or owns an ongoing cache in the sense invariant 3 targets, and
   `forced_flow` is itself terminal (COIN-M KILL, 2026-07-14). Moving them would touch closed-lane code for
   no invariant-3 benefit -- left exactly where they are, per invariant 5.

*Execution note 2026-08-25 (Task 15-16 deferred):* `research/exogenous/bybit_liquidation_feed.py`,
`research/exogenous/bybit_positioning.py`, their `tools/bybit_*_collect.py` CLIs, and their tests exist only
as **uncommitted work-in-progress** in the working checkout -- `git ls-files` confirms none of the five files
is tracked at any commit on `main`. The isolated worktree this phase executes in therefore does not have
them at all. Tasks 15-16 (giving these two domains a home in `collect/`) are deferred until that WIP is
itself committed to `main` by whoever owns it -- not a decision this phase's execution makes unilaterally.
Neither domain is a live cron path (confirmed via `crontab -l`: only `liquidation_collect.py` and
`deribit_chain_collect.py` are scheduled), so deferring them blocks nothing else in this phase.

*Done 2026-08-25:* `data/` stood up with nine domain modules (`http`, `ohlcv`, `series`, `bundle`,
`universe`, `orderbook`, `aggtrades`, `options`, `macro`, `vision` -- ten, correcting the plan's own
estimate) consolidating every fetch/cache implementation the spec's G4 paragraph named, plus the four
corrections Task 2 recorded. `core/data.py` and `core/series.py` relocated wholesale (no shim possible --
`test_core_imports_nothing_above_it` already forbade it); `core/bundle.py` split, keeping `DataBundle` as a
pure type and moving only `load_bundle`. `research/`'s six remaining fetch/cache modules (`universe_data`,
`aggtrades_data` -- updated directly at 2 importers, no shim needed -- orderbook's fetch half, `deribit_dvol`,
`fred_data`, `vision_klines`) kept thin re-export shims at their old paths for their combined ~115 remaining
importers, deferring their rewrite to G6's lane-by-lane conversion. `collect/` filled in with the two live
cron domains its G2 scaffold named (`deribit_chain`, `liquidation`); each got a hand-verified `status` read
against the live symlinked CSV after its commit, per hard constraint SS5.1 -- the live `collect` write-run
itself is deferred to after this branch merges, so no unreviewed code writes into the two production files
cron appends to every minute. `bybit_liquidation` and `bybit_positioning` (Tasks 15-16) are deferred
entirely: their source is uncommitted WIP on `main`, absent from this branch, and neither is a live cron
path. `research/forced_flow/coinm_archive.py` and the two one-time frozen-lane `tools/collect/` scripts
stayed untouched, out of scope per Task 2. The import-boundary test suite gained two new cases enforcing
`data`/`collect`'s one-way dependency on `core` (and, for `collect`, on `data`). The G3 reproduction gate
re-ran clean: `oibuild_study` still reproduces exactly; `liqladder` still fails to reproduce in exactly the
same two fields (`stouffer_z`, `pooled_mean`) for exactly the same already-recorded reason -- confirming
this phase's ~150 mechanical import-path edits changed no historical number. Two gotchas found beyond the
plan's own research: a monkeypatch-by-module-alias site in `tests/test_leadlag_signals.py` the plan didn't
name (fixed identically to the one it did), and a bare-submodule import (`from moonface.research import
universe_data`) that neither the mechanical rewrite tool nor a dotted-string grep can catch (the tool's own
docstring names this exact limitation) -- both confirmed via a full-tree grep to be the only instances of
each pattern. Suite `2658 passed`, `GUARD PASS`. `models/`, `strategies/`, and `lanes/` do not exist yet --
G5 and G6.

### G5 — `models/` and `strategies/`, and retiring the v2.2 runtime
Move the ~55 reusable files out of `signal/` into `models/` and `strategies/` per §1.5. Keep the
plugin API, registry, and entry points — they are the extension point for new work. Delete only the
v2.2 runtime: `cli.py`, `journal.py`, `notify.py`, `style.py`, `promotion/`, live-loop entry points,
and their tests.
*Green when:* suite green; `models`/`strategies` import no `kernel`; the four reference strategies
still load through the registry; G1 ruling still readable.

*Correction 2026-08-25 (pre-implementation):* five corrections to this section's "genuinely v2.2
runtime" list, found while researching the implementation plan:

1. `notify.py` is not v2.2-only -- `feed/cli.py` (the separate, independently-entry-pointed
   `moonface-feed` Telegram SMC broadcaster) imports `TelegramNotifier` from it, and lazily
   imports `_load_env_file` from `cli.py`. Both relocate into `feed/` before `cli.py` is deleted,
   rather than being deleted with it.
2. `journal.py` needs a split, not a delete: `append_entry`/`read_entries` are generic
   append-only JSONL I/O with no v2.2 coupling, and `tools/engine/engine_ablation.py` (paired
   with the kept `engine/ablation.py`) imports `read_entries` directly. Only `forward_report`
   (the promotion gate) is v2.2-specific and deletable.
3. `baseline.py` is imported by `engine/regime.py` (kept, moving to `models/`), not just `cli.py`
   -- it moves to `models/` rather than being deleted, despite its CLI-tier framing.
4. `participation_api.py` (one importer: `cli.py` itself) is deletable alongside `cli.py` but was
   not named in the spec's four-file list -- corrected here for completeness.
5. `strategy_api.py` has zero importers anywhere in the tree, including the four strategy modules
   its own docstring describes as importing "only from here". It still moves to `strategies/` per
   this section's explicit table entry (the intended plugin facade for future strategy authors,
   not dead lane code) -- flagged so a future phase does not mistake the zero-importer count for
   a deletion candidate without re-reading this note.

Full plan at `docs/research-log/plans/2026-08-25-g5-models-strategies.md`.

*Done 2026-08-25:* `models/` (engine/, matrix/, evaluate.py, baseline.py, journal.py's
append-only I/O half) and `strategies/` (strategy_api.py, registry.py, spec.py, impls/{donchian,
mtf_long, playbook, stack_path}) stood up; v2.2 runtime retired (cli.py, style.py,
participation_api.py, journal.py's forward_report half, promotion/{baseline,styles,
engine.json.example}); signal/ package removed. Two of the spec's four "genuinely v2.2 runtime"
files turned out to be shared with feed/ (the separate moonface-feed Telegram broadcaster) and
relocated there instead of being deleted -- correction recorded in this section pre-implementation,
with a second execution-time correction (notify.py/_load_env_file had to move atomically with
cli.py's deletion, not ahead of it, because test_import_boundaries.py already forbade signal/ from
importing feed/) folded into the deletion commit. `promotion/archive/` was kept, not deleted --
`tests/strategies/test_signal_spec.py::test_repository_archived_strategy_still_loads` loads a real
historical artifact from it as a schema-drift regression guard, found only by running the full
suite with it deleted. `tests/models/test_engine_cli.py` (misfiled during the file move: it
exercises `signal.cli`'s engine-mode routing, not the models/engine framework) was deleted
alongside `cli.py` rather than kept, once discovered.

`tests/test_import_boundaries.py` now enforces the real invariant-1 boundary (kernel forbidden
from importing models/strategies) in place of a dead signal-path check. All four reference
strategies confirmed loading through the registry. **Not fully green:** three files
(`models/engine/{audit,repair,calibration}.py`) import `moonface.kernel.bootstrap.
resample_by_block_key` -- pre-existing from when they lived under `signal/engine/`, not introduced
by this phase's file moves. This does not violate invariant 1 as stated (only `kernel` importing
`models`/`strategies` is forbidden; the reverse direction has no rule), and no test in this repo
checks it, but it does not satisfy this phase's own green-when line ("models/strategies import no
kernel") literally. Fixing it would mean promoting `resample_by_block_key` out of `kernel/` into a
shared location (`features/` or `core/`) that both `kernel/` and `models/` can import -- real
design work beyond "move signal/ content," left as a note for whoever picks this up next rather
than silently claimed clean or fixed unilaterally here.

### G6 — Convert lanes onto the kernel (not delete them)
Per lane, in isolation: run `impact` (GitNexus), express the lane as `registration.json` + a signal
function on the unified kernel, run it, and **append the result as a new run record**. The historical
record is never edited; the conversion run sits beside it.

| Comparison against the historical run | Action |
|---|---|
| Numbers match | The lane is now runnable on the kernel. Its bespoke code is **redundant**, not obsolete, and may be removed |
| **Numbers differ** | Two valid records now exist. **Delete nothing.** The delta is the finding — it may mean the old pipeline was wrong, or the new one is, and which is a question for a human |
| Cannot be expressed on the kernel | Keep the lane's code. It is the only way to re-derive its record |

Note the shift from the earlier draft: the deletion criterion is **redundancy**, never a lane's
result. A lane whose runs were all negative is as re-runnable as any other — under §1.1 that is not
a reason to touch it. A module with ≥3 importers outside its own lane is not a lane: promote it to
`features/` and rename it. **No lane-count target is committed.**
*Green when:* suite green after every single lane; every conversion appended, none overwritten;
collectors verified at phase end.

### G7 — The forward workflow
Implement §3.1 end to end and prove it the only way that counts: **stand up one new lane from
scratch** through `research new → power → register → run`, and confirm the cost is a registration
plus a signal function rather than a new script. Encode power-before-lockbox and fail-on-iid-null
as tooling, not convention.
*Green when:* a new lane reaches a recorded run without a line of bespoke pipeline.

### G8 — Normalize the ledger into run records
Consolidate ≥3 schemas into `experiments/registry/<lane>/runs/<run_id>/`. Real work, not a move: 74
of 84 lanes are outside the machine-readable schema.

Migration rule, from §1.1: an existing `verdict.json` becomes a **run record of the run that
produced it** — its numbers, window, and date are preserved verbatim; its *conclusion* fields
(`verdict`, `reason`, any CLOSED/OPEN status) are moved into that run's `report.md` as the
historical narrative and are **not** carried into `result.json`. The claim is demoted from a
property of the lane to a sentence someone wrote on a date. Nothing is lost; it stops being
authoritative.
*Green when:* record count before == after; no `result.json` carries a status or verdict field; the
12 human-readable `report.md` files preserved verbatim (never re-parsed).

## 5. Hard constraints

1. **Two collectors are live.** `crontab` runs `tools/liquidation_collect.py` and
   `tools/deribit_chain_collect.py` every minute with hard-coded paths. Deribit is 24 days into a
   ~150-day clock toward a 2027-01-25 gate; a silent break costs the clock. Paths must not change.
   Contents may, but every commit touching collector code is followed by a manual run and a
   row-count check. Snapshot `chain_BTC.csv` before G2 — the first phase that touches code.
2. **`.backtest_cache/` and `cache/` are frozen until G6 completes.** They are the deterministic
   substrate of the G3 gate and of every lane conversion at G6 — not disposable cache. G0 leaves
   them alone despite their size.
3. **Every phase is one commit ending on a green suite.**

## 6. Risks

| # | Risk | Control |
|---|---|---|
| R1 | Silent collector breakage → lost Deribit clock | Paths frozen; manual run + row-count after every touching commit; pre-G2 snapshot |
| R2 | Source-data drift makes the G3 gate report a false kernel failure | Gate runs offline on `.backtest_cache/`; caches frozen through G6; any tolerance recorded |
| R3 | Deleting infrastructure disguised as a dead lane (`oibuild_study` 19 importers, `edge_search` 15, `system_battery` 13, `xsection` 12) | One lane at a time; `impact` before, full suite after; ≥3 external importers ⇒ promote, never delete |
| R4 | A run record lost while normalizing ≥3 ledger schemas | Record count before == after; `report.md` verbatim |
| R5 | Unified kernel silently changes the behaviour of the 12 DSR variants | Exactly what the G3 gate detects; divergence at G6 is recorded as a finding, not smoothed over |
| R6 | Data unification changes historical numbers (different cache path or rounding) | G4 runs the G3 gate again afterwards; the recorded runs must still reproduce |
| R7 | `models/` extraction quietly drops a v2.2-coupled behaviour that lanes rely on | 105 test files touch `signal`/`feed`; they move with the code and must stay green |

## 7. Success criteria

**Trust — re-derivable run records, currently 10 of 84.** Every lane converted at G6 whose numbers
reproduce joins that count. The aspiration is ~45; **no number is committed.** A lane that diverges
stays uncut and the delta is recorded as a finding.

**Comparability — every run record carries the provenance triple** (§3.2), so any two runs of a
lane can be diffed *and the delta attributed* to params, data, or code. Today zero records carry it.
Determinism is checked, not assumed: same triple ⇒ same numbers.

**Epistemic hygiene — zero conclusions in the ledger.** After G8 no `result.json` carries a status
or verdict field, and no tooling can write one. Measured directly: grep the registry for status and
verdict keys, expect zero hits. This is the criterion that keeps the other two honest, because the
program's two known failures — a false kill that survived, and a ruling wrong twice — were both
conclusions that outlived the evidence supporting them.

**Capability — the cost of the next hypothesis.** Today: ~300 lines of bespoke pipeline. Target
(proved at G7): a registration plus a signal function, on a kernel that has demonstrated it can
re-derive a known run.

Structural: one verification path; one data path; zero `kernel`→`models` and zero `kernel`→lane
edges; zero lane→lane edges; the strategy plugin API intact and exercised; collectors uninterrupted
throughout; verify loop < 60 s.

**Explicit non-goal: file count.** Shrinkage is a side effect of replacing 16,393 lines of divergent
pipelines and ~20 ad-hoc data loaders with one kernel and one data layer. No phase is judged by it.
