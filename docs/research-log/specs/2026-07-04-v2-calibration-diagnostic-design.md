# Confluence Engine v2 — Score-Calibration Diagnostic (Design Spec, 2026-07-04)

**Mandate (human, 2026-07-04):** Continue research on Confluence Engine v2 signal
quality as an **offline, read-only diagnostic lane**. The v2 forward-paper record and
its frozen registration (`experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md`,
FROZEN 2026-07-04, hash `10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf`)
are untouched: the clock keeps running, no frozen constant changes, no candidate v2.1.

**The one pre-registered question:** *does the v2 confluence score order trade
outcomes on history?* If score buckets do not order by expectancy, the weights are
noise and no threshold placement can fix it. If they do, the score is informative and
the forward record is measuring something real. Approved approach: full-distribution
hypothetical-trade calibration (A), with per-module IC decomposition (C) as a
non-verdict-bearing secondary.

Related documents:
- v2 registration: `experiments/engine/CONFLUENCE_V2_FORWARD_REGISTRATION.md`
- v2 spec/plan: `docs/research-log/specs/2026-07-03-confluence-engine-v2-design.md`,
  `docs/research-log/plans/2026-07-03-confluence-engine-v2.md`
- v2-only refocus: `docs/research-log/specs/2026-07-03-v2-only-refocus-design.md`

## 1. Governance envelope (hard constraints)

1. **Zero edits to any existing engine module.** New read-only files only, following
   the `honesty.py` / `ablation.py` precedent for diagnostic modules beside the engine.
2. **`engine_hash` invariance is tested:** `engine_hash(EngineConfig())` equals the
   frozen registration hash before and after this lane; importing/running calibration
   code cannot change it (the hash covers ENGINE_VERSION + config + frozen-constants
   digest; this lane adds files and touches none of those).
3. **Criteria frozen before the run.** The report skeleton (§6) with pass/fail
   criteria, floors, and assumptions is committed before any real-data run.
4. **Diagnostic verdict vocabulary only:** CALIBRATED / PARTIALLY CALIBRATED /
   UNCALIBRATED / UNDERPOWERED, each with stated implications for *interpreting* the
   forward record. The report never recommends a constant change. Any future v2.1 is a
   separate human decision requiring a new ENGINE_VERSION, hash, and registration.
5. **No changes** to `promotion/`, `journal/signals.jsonl`, registration text, or any
   frozen constant. The lane does not read the forward journal at all — history only.

## 2. Components (both new, read-only)

### 2a. `src/moonface/signal/engine/calibration.py` — pure functions, no I/O

**Scoring pass.** Per closed bar, call the same frozen functions `evaluate_engine`
calls, in the same order, over the same rolling `lookback_bars = 6000` window:
`trend_book.build_views` → `classify_regime` → `classify_macro` →
`trend_book.score` / `revert_book.score` → `decide`, with `deriv=None`. Record a rich
per-bar row the journal schema does not carry:

- per-book signed score, direction, and breadth — reconstructed from
  `Decision.modules` (module names are disjoint across books: `m1_macro`,
  `m2_breakout`, `m2_ma_align`, `m3_roc`, `m4_pullback`, `m5_funding` vs `m1_sweep`,
  `m2_reclaim`, `m3_divergence`, `m4_fund_ct`, `m5_oi_flush`, `m6_stretch`);
- macro effective state and the gate policy per book (ALLOW / ALLOW_CT / REJECT);
- per-module signed points and `data_ok` flags;
- regime trend / vol state;
- `revert_book.sweep_state(views.h1)` wick extreme (for CT hypothetical entries,
  mirroring `engine.py`'s CT sweep-wick lookup).

**Hypothetical-trade simulator.** At any bar where a book has nonzero direction —
regardless of threshold — open a position with the frozen `open_position` and manage
it bar-by-bar with the frozen `manage_position` until EXIT:

- TREND-book entries use the WT profile (ATR ratchet trail, `cfg.max_bars` time stop).
- MEAN_REVERT-book entries use the CT profile (sweep-wick stop where a same-direction
  sweep exists, fixed 2R target, 24-bar time stop) — profile follows the book, not the
  gate policy, so CT mechanics are exercised across the whole score range.
- Outcome per event: net R (`realized_r` from the frozen `_exit` path, cost included),
  bars held, exit reason, plus the entry row's score/context fields.

**Aggregation.** Per-bucket expectancy, Spearman rank statistics with moving-block
bootstrap CIs, half-splits, book/direction/gate/regime splits, per-module IC table.

### 2b. `tools/engine_calibration.py` — thin CLI

Load cached candles (`load_bundle`, same as `engine_backtest.py`), run the scoring
pass and simulator, emit a JSON report (conventions of `engine_honest_report`: pure
`build_report` function + thin CLI; `--start-ms/--end-ms/--cache-dir/--out`).

### 2c. Forward-parity claim, stated precisely

Parity is at the **function** level (identical frozen scoring and exit functions on
identical rolling windows), not the orchestration level — `evaluate_engine` itself is
bypassed because it couples scoring to journal state (open positions, kill-switch,
cooldown), which would suppress exactly the sub-threshold coverage this lane measures.
A parity test pins the claim: on a fixture window, the scoring pass's `Decision` must
equal `evaluate_engine`'s `Decision` bar-for-bar while flat.

## 3. Data & runtime

- **Series:** fingerprinted cache `.backtest_cache/BTC_USDT:USDT_1h.csv`, 2020-01 →
  2026-07 (~56.8k bars); fingerprint recorded in the report.
- **Warmup:** first scored bar has a full 6000-bar window, so the 1W macro gate is
  live from bar one (≥31 weekly closes) — no NEUTRAL-macro warmup regime polluting
  the gate splits.
- **`deriv=None` caveat (first-class):** the replay scores the price-structure core
  only — the TREND book caps at 85/100 (no `m5_funding`) and the MEAN_REVERT book
  loses `m4_fund_ct` + `m5_oi_flush`. The verdict applies to the price-structure core;
  the live engine additionally sees derivatives confirmation. This is the report's
  caveat #1.
- **Runtime:** same order as the existing honest-report replay (known feasible over
  6.5y); the simulator adds at most `max_bars` management steps per event.

## 4. Methodology

### 4a. Sampling (two complementary samples, one pass)

1. **Overlapping event panel (primary).** Every bar with nonzero book direction is a
   hypothetical entry. Full coverage of the score range; overlapping outcomes →
   all CIs use a moving-block bootstrap with block length 7 days of bars (168),
   ≥ the typical holding period.
2. **Non-overlapping stream (robustness).** One position at a time per book,
   threshold-free — the live engine's sequencing shape. Confirms the panel result is
   not an artifact of overlap weighting.

### 4b. Reversal-exit assumption

Hypothetical trades run the frozen discipline **without** the opposite-SETUP reversal
exit (sub-threshold bars have no tiered SETUPs, so the rule is undefined there). A
sensitivity check runs the actual-trigger subset (score ≥ frozen threshold) both with
and without reversal exits; the resulting bound on expectancy distortion goes in the
report.

### 4c. Pre-registered criteria (frozen before the run)

- **Primary, per book:** Spearman ρ between score-at-entry and net R over the
  overlapping panel. *Calibrated* = ρ > 0 with 95% block-bootstrap CI excluding 0,
  **and** bucket expectancy weakly increasing across the four frozen-edge buckets
  <40, 40–59, 60–74, ≥75 ("weakly increasing" = each bucket's mean net R ≥ the
  previous bucket's, evaluated on point estimates).
- **Stability:** sign of ρ agrees across the 2020-01→2023-04 / 2023-04→2026-07 halves.
- **Splits reported, never gated:** book × direction; gate policy (ALLOW / ALLOW_CT /
  vetoed-shadow); regime vol state; per-bucket n so underpowered cells are visible.
- **Power floor:** any book whose panel has < 200 events, or whose ≥60 bucket has
  < 30 events, is UNDERPOWERED for that book — regardless of whether its statistics
  would pass or fail (floors stated here, not tuned later).
- **Verdict (one, written once):** each book is first classified UNDERPOWERED / pass /
  fail; then —
  - CALIBRATED — both books pass primary + stability;
  - PARTIALLY CALIBRATED — exactly one book passes (the other fails or is
    UNDERPOWERED, named);
  - UNCALIBRATED — neither passes and at least one affirmatively fails;
  - UNDERPOWERED — both books are below the power floor.

### 4d. Secondary — per-module IC decomposition (approach C)

From the same pass: rank-IC of each module's signed points vs 24h forward log return,
Newey–West t (lag = 24). Explicitly labeled **suspect-ranking if calibration fails** —
never verdict-bearing: fixed-horizon drift has repeatedly failed to survive brackets
in this program's record, so module IC is a pointer for future lanes, not evidence of
tradeable quality.

## 5. Testing (TDD, repo conventions)

- **Parity:** scoring pass `Decision` == `evaluate_engine` `Decision` bar-for-bar on a
  fixture window while flat.
- **Hash invariance:** `engine_hash(EngineConfig())` equals the frozen registration
  hash with calibration modules imported.
- **Simulator:** hand-computed WT (trail ratchet, time stop) and CT (wick stop, 2R
  target, 24-bar stop) exits on synthetic candles; net-R cost arithmetic matches
  `position._net_r` behavior via the public path.
- **Aggregation:** bucket/Spearman/bootstrap on synthetic fixtures with known answers;
  monotone fixture → CALIBRATED shape, shuffled fixture → UNCALIBRATED shape.
- **Degenerate inputs:** all-WAIT history, single-direction history, empty panel →
  clean UNDERPOWERED/empty report, no crash.
- Full suite stays green; ruff clean.

## 6. Deliverables & ordering

1. `experiments/engine/CALIBRATION_DIAGNOSTIC_2026-07.md` — skeleton committed
   **before** the run: question, criteria (§4c verbatim), floors, assumptions
   (§3 caveat, §4b), verdict vocabulary. Results and the single verdict appended
   after the run.
2. `src/moonface/signal/engine/calibration.py` + `tools/engine_calibration.py` +
   tests.
3. This spec force-tracked per the v2-lane convention (docs/ is globally ignored;
   v2 spec/plan were deliberately tracked in c896a57).

Ordering constraint: tests + skeleton (criteria frozen) → real-data run → results +
verdict appended → no edits to criteria afterward.

## Out of scope

Changing any frozen constant, threshold, weight, or gate entry; producing candidate
v2.1 constants; touching `promotion/`, the forward journal, or registration text;
starting/stopping the watch daemon; reopening any closed research lane; any claim of
validated edge (the NO_CLAIM posture rides on everything).
