# TDA Correlation Topology — Design Spec

- **Lane:** `tda_topology_v1`
- **Date:** 2026-07-16
- **Kind:** descriptive research instrument (NOT a gate, NOT an edge lane)
- **Status:** design — awaiting implementation plan
- **Source idea:** `docs/research-log/concepts/crypto_geometric_signal_research_ai_readable.md`
  (Hướng 1 "Cosmic Web → Dynamic Market Graph", Hướng 4 "Topological Data Analysis")

## 1. Problem and positioning

The source document proposes six geometric research directions. Five of them map onto
axes this program has already closed:

| Doc direction | Prior verdict |
|---|---|
| 1. Cosmic Web → Dynamic Market Graph | H1 = crypto beta (`breadth-neutral`, hedged edge flips sign); H3 = `lead_lag` CLOSED 2026-06-11; H2 = `xsection_perp` CLOSED (sealed tail −91.6% DD) |
| 2. Fractal Geometry | `donchian-adx-filter`, `donchian-volregime`, `regime-overlay` (0/12), `regime-selector` (filter subtracts) all CLOSED; `stack_path` (path geometry) CLOSED 2026-07-16 |
| 3. Gyroid → Manifold | `macro-regime-instrument` CLOSED FRAGILE (GMM labels rank-flip across eras); `regime-moe` all trials closed |
| 5. Einstein Ring → Conditional amplification | = regime gating; `matrix-step-a-router` CI on n=36 = coin flip |
| 6. Spiral / Fibonacci | doc itself does not recommend; agreed |
| **4. Topological Data Analysis** | **never run in this program** |

The umbrella finding that covers directions 1/2/3/5 is `market-state-microscope-lane`
(2026-07-10): on 1838 Donchian events with 6 buckets ≥ POWER_FLOOR, forward-R does **not**
stratify by regime (real effect 0.609 vs shuffle p95 0.835; the effect moved *further* into
the null as events doubled). There is nothing to gate on.

TDA is the one technique in the document with no prior verdict here. This instrument exists to
answer exactly one question and then stop:

> Does persistent homology of the cross-sectional correlation matrix stratify the forward-R
> distribution of the same 1838 Donchian events, beyond a null that preserves time structure?

**Why TDA is worth a run when the graph approach is not.** The document warns at §13.5 that
*"graph threshold có thể tạo degree of freedom lớn"* and then at §14 specifies
`threshold_method: top-k edges per node` anyway. Persistent homology reads the correlation
matrix at **every threshold simultaneously** — persistence *is* "how many thresholds does this
structure survive". So TDA is not a fourth direction parallel to the graph; it is the
threshold-free version of direction 1. One instrument answers both, and it removes the single
largest degree of freedom the document introduces.

**Governance.** The free-data addendum (`68ca474`, approved 2026-07-06) sets a terminal rule:
the remaining free-data budget is three hypotheses (H3 `advval` KILL, H1 `eventtime` KILL, H2
`liqprem` outstanding), with no reopening under any framing. This lane does **not** spend that
budget and does not violate the rule, because it makes no edge claim: no gate, no DSR ladder,
no lockbox, no promotion path. It is an instrument, positioned exactly as
`market-state-microscope-lane` was ("explicitly NOT regime-filter attempt #9"). Human approval
for this positioning was given 2026-07-16.

## 2. Scope

**In scope.** Persistent homology (H0, H1) over rolling Spearman correlation of a 17-asset 4h
return cross-section; seven causal topology features per bar; frozen-threshold market-level
regime labels; a conditional event study over the existing 1838 Donchian events; a
time-structure-preserving null calibration; one report.

**Out of scope (v1).** Time-delay (Takens) embedding of single series — a different point-cloud
construction, considered and rejected at design time as it re-reads BTC path geometry, the
exact substrate `stack_path` and `drift_screen` have already exhausted. H2 homology (expensive
and uninterpretable at 16 points). Mapper graphs. Persistence-image ML features. Any strategy,
gate, sizing, or promotion. Any coupling to `confluence v2.2` or the frozen forward
registrations. Any fetch of new data.

**Explicitly forbidden.** Re-running at a different window W to rescue a negative result
(see §7).

## 3. Architecture

Quarantined under `experiments/tda_topology/`, mirroring the `experiments/macro_regime/`
precedent: the main tree is stdlib-only and `pyproject.toml` sets `testpaths = ["tests"]`, so
`numpy`/`scipy`/`ripser` must not enter `src/`.

```
experiments/tda_topology/
  DESIGN.md            # pointer to this spec
  README.md            # how to run
  requirements.txt     # numpy, scipy, ripser (fallback: gudhi)
  .gitignore           # .venv/, *.csv artifacts
  .venv/               # own venv; pip install -e . for the main package
  tda_features.py      # point cloud -> persistence diagrams -> features
  tda_labels.py        # features -> frozen-threshold labels
  run.py               # offline orchestrator
```

The quarantined venv installs the main package editable so it can reuse
`moonface.foundation.{bundle,risk}` and `moonface.research.microscope.events` — all of which
are stdlib-only and therefore import cleanly. **The main tree changes zero lines.**

### 3.1 Data loading — cache-only, offline

Candles come from `cache/matrix/{SYM}_4h.csv` (OhlcvCache format, 17 symbols, already warm).
Correlation topology needs returns only, so this lane needs **no OI, no funding, no bookdepth**
— it skips the entire fetch cost that dominated the microscope run (~8 min/asset for OI
metrics). The loader must be cache-only and must fail loudly if a symbol is missing rather than
silently shrinking the cross-section (microscope run gotcha #1: the pool silently collapsed to
BTC-only and every event went UNLABELED).

Universe = the 17 symbols in `tools/microscope.py:UNIVERSE` — the 16 frozen `drift_screen`
assets plus `BTCUSDT`. Window 2020-01 → 2026-06-30.

**Note a deliberate deviation from the source document.** Its MVP (§14) proposes a universe
built around BTC/ETH/SOL. This lane uses the frozen microscope/`drift_screen` universe instead,
which contains **no ETH and no SOL**. That is the point: it is the universe the 1838 events were
generated on, so reusing it adds zero new degrees of freedom and keeps the microscope
head-to-head valid. Choosing the document's universe would require regenerating the event set
and would make the comparison meaningless.

### 3.2 tda_features.py — point cloud to features

For each bar `t` on the common timestamp grid:

1. Collect trailing `W` log-returns for every asset with a complete window. If fewer than
   `XS_MIN_ASSETS = 8` assets qualify, emit `None` features for that bar (they become
   UNLABELED downstream).
2. Spearman correlation matrix `ρ` across the qualifying assets (Spearman per source doc §14
   `rolling Spearman correlation of returns`).
3. Distance matrix `d_ij = sqrt(2 * (1 - ρ_ij))` — the standard correlation metric; it is a
   true metric for `ρ ∈ [-1, 1]` and maps ρ=1 to d=0, ρ=-1 to d=2.
4. Vietoris-Rips persistent homology on `d`, `maxdim=1`.

Seven features per bar, all computed from the trailing window only:

| Feature | Meaning |
|---|---|
| `pers_entropy_h0` | entropy of H0 lifetimes — how evenly the market fragments into clusters |
| `pers_entropy_h1` | entropy of H1 lifetimes |
| `total_pers_h0` | summed H0 lifetimes — total cluster structure |
| `total_pers_h1` | summed H1 lifetimes — total loop structure (doc T2 "rotational structure") |
| `landscape_l1_h1` | L1 norm of the H1 persistence landscape (Gidea-Katz readout) |
| `landscape_l2_h1` | L2 norm of the H1 persistence landscape (Gidea-Katz readout) |
| `wasserstein_dist` | Wasserstein distance between the diagrams at `t` and `t-1` (doc T3 "topology break") |

`wasserstein_dist` is `None` when bar `t-1` has no valid diagram (fewer than `XS_MIN_ASSETS`
qualifying assets, or `t` is the first valid bar). It does **not** reach further back to find
the most recent valid diagram: that would silently compare across a gap of unknown length and
make the feature mean different things at different bars. A `None` here makes the bar
`UNLABELED`, which is the honest outcome.

`W = 60` bars (10 days at 4h) is the **primary and only** window for the verdict. It is the
middle of the document's proposed 30/60/120; running all three as separate verdicts would be a
3× multiple comparison on an instrument with no correction. W ∈ {30, 120} may be run and
reported as robustness texture only — never as an independent verdict (§7).

**Causality.** Every feature at bar `t` uses only bars `≤ t`. `wasserstein_dist` uses `t` and
`t-1`, both in the past. A test asserts feature values are unchanged when future bars are
truncated (§6).

### 3.3 tda_labels.py — frozen-threshold labels

Two axes, four buckets:

- **Concentration axis** — `pers_entropy_h0`. Low entropy = few dominant clusters =
  `CONCENTRATED`; high = `DISPERSED`.
- **Stability axis** — `wasserstein_dist`. Large = `BREAK`; small = `STABLE`.

Label = `{CONCENTRATED|DISPERSED}/{STABLE|BREAK}`.

**Thresholds use an expanding trailing quantile, never a global one.** A global quantile over
the full sample is look-ahead: the label at bar `t` would depend on bars after `t`. Each axis
splits at its expanding-window median (50th percentile of all values from the burn-in start
through `t-1`), with a burn-in of `BURN_IN = 250` bars before any label is emitted. Bars inside
burn-in, or with `None` features, are `UNLABELED` and excluded by `bucket_report`.

Thresholds are frozen here in the spec and must never be tuned against study outcomes — that
would convert the instrument into a fitted regime model, which is precisely what it is not.

**Expected bucket sizes.** Measured 2026-07-16: the 1838 events fall on **1215 distinct bars**
(mean 1.51 events/bar; 897 bars carry exactly one). A market-level label therefore has an
effective N of ~1215, and a 4-way median split gives roughly 300 bars per bucket — comfortably
above `POWER_FLOOR = 30`. This lane is powered before it is run (the
`matrix-step-a-router` lesson: check power before, not after).

### 3.4 Event study — reused verbatim

The label is **market-level**: one value per bar, broadcast to every symbol at that bar to
produce `labels[sym][t]`. This is the interface
`moonface.research.microscope.events` already takes, so `event_outcomes`, `bucket_report`,
`effect_size` and their constants (`HORIZONS = (6, 12, 42)`, `PRIMARY_HORIZON = 12`,
`POWER_FLOOR = 30`, `K_ATR = 2.0`, `ATR_PERIOD = 14`) are reused **verbatim, unmodified**.

Events: `experiments/microscope/donchian_universe_events.csv` (1838 rows, 17 symbols, all
`direction=1`). Reusing the frozen event set is deliberate — it makes the result directly
comparable to the microscope's 0.609 / 0.835 baseline, and it adds zero new degrees of freedom.

**Scope caveat, inherited and unfixable in v1:** all 1838 events are long-only, so they fire
mainly in UP-ish regimes. RANGE is thin and DOWN is absent. A negative verdict therefore closes
the geometric axis *for long trend-breakout entries*, which is the same scope the microscope's
finding already has. A long+short event source would be a different lane.

### 3.5 Null calibration — the one place this lane departs from the microscope

`microscope.events.null_calibration` shuffles labels **row-wise**. For the microscope that was
defensible: labels were per-symbol, so each row carried its own draw. Here the label is
market-level and derived from a rolling `W = 60` window, so it is **strongly autocorrelated** —
labels arrive in long runs. Row-wise shuffling destroys those runs, which shrinks the null
effect distribution and makes it **too easy to beat**, inflating the false-positive rate. That
is the `vol-compression` failure mode in a new costume: a null that cannot reproduce the
structure of the real thing is not a null.

So this lane implements `block_null_calibration` in `run.py`:

- Permute the **label time series** by circular block permutation with `BLOCK = 30` bars,
  preserving run length and within-bar clustering; re-derive row labels from the permuted
  series; recompute `effect_size`. `N_SHUFFLES = 200`, seeded.
- Verdict: `EXCEEDS_NULL` if `real_effect > null_p95 and real_effect > 0`, else
  `INDISTINGUISHABLE_FROM_NULL` — same rule shape as the microscope.
- The microscope's row-wise `null_calibration` is **also** run and reported, as a secondary
  diagnostic, to make the gap between the two nulls visible rather than asserted.

**No `beta=0 ≡ raw` anchor is available here**, and claiming one would be false. The
`breadth-neutral` anchor worked because hedging at beta=0 reduces to the unhedged computation
on the *same* rows. These two nulls act on different objects — the row null permutes labels
across 1838 outcome rows, the block null permutes a 1215-bar label series that is then
broadcast — so no parameter setting makes them coincide. `block=1` does not reduce to the row
null; it reduces to a plain permutation of the *bar* series, which is the bar-level analogue,
not an identity. The testable invariants are therefore on `circular_block_permute` itself
(§6), and the two nulls are compared as two numbers in the report, not asserted equal.

This is a deliberate asymmetry and it is not apples-to-apples in the strict sense: the block
null is *harder* to beat than the row null the microscope faced. That direction is the correct
one to err in — it can only suppress a false positive, never manufacture one. If the real
effect fails even the row-wise null, the block null is moot and the verdict is negative a
fortiori.

### 3.6 run.py — outputs

Writes to `experiments/tda_topology/` (gitignored): `features.csv` (per-bar features),
`labels.csv` (per-bar labels), `outcomes.csv` (per-event rows), `report.md` (bucket table,
both null calibrations, head-to-head against the microscope's 0.609/0.835 baseline),
`run.log`.

`report.md` must state the verdict once, and state the scope caveat from §3.4 next to it.

## 4. Honesty guardrails

1. **NOT-A-GATE.** No pass/fail is emitted for any trading decision. No lockbox, no seal, no
   DSR ladder, no promotion path, no `EXIT_REGISTRY` or journal writes.
2. **A valid instrument must fail on a null.** The iid self-test (§6) is a build-time
   requirement, not a nice-to-have — the `vol-compression` lane produced the program's first
   ever PASS and it was an artifact that an iid null would have caught.
3. **Thresholds and W are frozen in this spec** before any outcome is inspected.
4. **No parameter rescue.** See §7.
5. **Buckets below `POWER_FLOOR` report their size and nothing else** — no direction, no CI.
6. If `EXCEEDS_NULL` fires, the result is a **hypothesis-generator only**. The microscope's
   own history is the precedent: two buckets had CIs excluding zero, null calibration flagged
   them as multiple-comparison artifacts across 14 buckets, the one replicated texture
   ("buying euphoria") got a pre-registered lane, and that lane
   (`euphoria-fade-results`) closed negative. Texture is not edge.

## 5. Data flow

```
cache/matrix/{SYM}_4h.csv  (17 syms, cache-only, no fetch)
        |
        v
  aligned log-return matrix on common 4h grid
        |
        v   per bar t, >= 8 assets with full trailing W=60
  Spearman rho  ->  d = sqrt(2(1-rho))  ->  Vietoris-Rips PH (maxdim=1)
        |
        v
  7 causal features per bar            -> features.csv
        |
        v   expanding-median thresholds, BURN_IN=250
  market-level label per bar           -> labels.csv
        |
        v   broadcast to labels[sym][t]
  microscope.events.event_outcomes  (VERBATIM)
        |
        +--> bucket_report  -> per-bucket fwd_r/MFE/MAE/stop-rate
        +--> effect_size    -> spread of mean fwd_r_12 across powered buckets
        +--> block_null_calibration (primary, BLOCK=30)
        +--> null_calibration       (secondary diagnostic, row-wise)
        |
        v
  report.md  (verdict + scope caveat + microscope head-to-head)
```

## 6. Testing strategy

Correctness lives in the topology, not the finance. Tests run inside the quarantined venv.

| Test | Assertion |
|---|---|
| Known topology: circle | a point cloud sampled from a circle yields exactly one long-lived H1 class |
| Known topology: two clusters | two well-separated blobs yield exactly two long-lived H0 classes |
| Causality | features at bar `t` are bit-identical when the series is truncated at `t` vs `t+500` |
| Block-permute invariants | `circular_block_permute` with `block=1` returns a permutation of the input (multiset equality); with `block=len(seq)` returns a rotation of the input |
| iid null self-test | iid Gaussian returns through the frozen pipeline yield `INDISTINGUISHABLE_FROM_NULL` |
| Cross-section floor | a bar with 7 qualifying assets emits `None` features; 8 emits real ones |
| Burn-in | bars before `BURN_IN` are `UNLABELED` |
| Determinism | two runs with the same seed produce identical `report.md` |

## 7. Stop rule

- `INDISTINGUISHABLE_FROM_NULL` → the geometric axis from the source document is **closed**.
  Record the verdict in `docs/findings/BACKLOG.md` and in memory. No v2, no window rescue, no
  alternate point-cloud construction as a follow-on.
- `EXCEEDS_NULL` → hypothesis-generator only (§4.6). It earns a *separately pre-registered*
  lane on a fresh seal, which requires a human decision on the free-data terminal rule. It does
  not earn a strategy.

**The window trap, stated explicitly.** If W=60 is negative and W=30 or W=120 looks better,
that is the parameter rescue this rule forbids. `stack_path` closed on 2026-07-16 with exactly
this shape: its descriptive curve decayed monotonically and `h=6` was the flattering row that
cleared nothing — re-running there would have been the rescue. The same discipline applies to
`BLOCK`, `BURN_IN`, and the label thresholds.

## 8. Cost and risk

Rips on a 16-point distance matrix is microseconds; ~14k bars × 17 assets with a warm cache
puts the run in minutes, comparable to `stack_path` (100s). No network, no fetch, fully
offline and re-runnable.

**Principal implementation risk:** `ripser` builds from source on Python 3.12 and may fail.
The first task in the plan is an install spike; fallback is `gudhi`, which ships wheels. If
both fail, a pure-`scipy` Vietoris-Rips for `maxdim=1` on ≤17 points is a tractable last resort
(the complex is tiny), but it is a last resort — not the plan.

## 9. Deliverable mapping to the source document

| Doc item | Delivered as |
|---|---|
| §7 TDA: `persistent_homology`, `persistence_diagram`, `persistence_landscape`, `betti_numbers` | §3.2 features |
| §7.4 T2 "persistent loops = rotational structure" | `total_pers_h1`, `pers_entropy_h1` |
| §7.4 T3 "topology break precedes vol expansion" | `wasserstein_dist` + `fwd_vol` in `bucket_report` |
| §4 Dynamic Market Graph (density, modularity, community_count, spectral_gap, graph_entropy) | subsumed threshold-free — persistence over all thresholds replaces top-k edge selection (§1) |
| §11 null models: `block_bootstrap`, `regime_label_permutation` | §3.5 block permutation (primary) + row-wise (diagnostic) |
| §10 Phase 1 "descriptive research" | this entire lane |
| §10 Phase 3 "signal gating", Phase 4 "standalone strategy" | **not delivered, by design** — §4.1 |
| §7.2 `mapper_graph`; §5 Fractal; §6 Manifold; §8 Einstein Ring | out of scope (§2) — closed axes per §1 |
