# v2 Scoring Component & Weight Audit — Design (staged, read-only)

**Date:** 2026-07-05
**Status:** Approved design (brainstorm complete). Implementation plan to follow.
**Origin:** User mandate — before any "more signals / LONG+SHORT" work, audit
the scoring components and weights: does each contribute useful signal, are
the current weights justified by evidence, and could a scoring/weighting
issue explain the weak signal quality? No changes to the engine yet.

## 1. Objective & posture

Answer two questions about the frozen v2 scoring core, per book and **per
direction** (TREND-LONG, TREND-SHORT, MEAN_REVERT-LONG, MEAN_REVERT-SHORT):

- **(a) Component contribution:** does each of the 12 modules contribute
  outcome-ordering signal under the current design?
- **(b) Weight justification:** are the hand-set weights (round numbers,
  never fitted) justified — could *any* nonnegative reweighting produce
  out-of-sample ordering where the current weights do not?

The per-direction tables are first-class outputs: they are the evidence a
future SHORT-side decision needs.

**Posture (binding):** read-only, identical to the 2026-07 calibration
diagnostic. No engine constant, config (`promotion/engine.json`), journal, or
registration text changes; the v2.1 forward-paper clock
(`CONFLUENCE_V21_FORWARD_REGISTRATION.md`, hash `4e35561f…`) is untouched.
Criteria are frozen in a pre-registration doc
(`experiments/engine/SCORING_AUDIT_2026-07.md`) before each stage's run; one
run per stage (re-runs only for mechanical failure); verdict written once.
The audit recommends nothing automatically — its output feeds a separate,
human-gated v2.2 / expansion decision.

## 2. Context (evidence baseline)

- v2.1 frozen 2026-07-04: BTC/USDT:USDT 1h, paper-only, long-only, no CT,
  single tier (threshold 60). Any constant change = v2.2 → new hash → new
  registration → fresh clock.
- Calibration diagnostic 2026-07 (`CALIBRATION_DIAGNOSTIC_2026-07.md`),
  verdict UNCALIBRATED: TREND ρ = 0.052 (CI-clean) but monotonicity fails at
  ≥75; ordering concentrated in LONG (+0.0683 mean R) vs SHORT (−0.1418) and
  high-vol bars. MEAN_REVERT ρ ≈ 0, every bucket negative. No module has
  |NW t| ≥ 2 on the fixed-horizon IC table.
- **Known blind spot:** that run used `deriv=None` — the three derivative
  modules (`m5_funding` trend; `m4_fund_ct`, `m5_oi_flush` revert) have never
  been evaluated, although the live engine scores with them.
- Weights are hand-set constants (10–25 points, sum 100 per book) in
  `modules/trend_book.py` and `modules/revert_book.py` — designed, not
  fitted.

## 3. Staging

- **Stage 1 — price-structure core (9 modules), now.** Reuses the existing
  harness; deriv stays None. Mostly new analyses on the proven panel.
- **Stage 2 — deriv-inclusive (all 12 modules).** Gated on Stage 1 completing
  AND the deriv-history data path passing its integrity checks. Reruns the
  entire Stage-1 battery with historical deriv snapshots populated.
- Stage-2 criteria get their own frozen section in the pre-reg doc written
  *before* the Stage-2 run: blind to any new deriv numbers, but it may cite
  already-published Stage-1 facts.

## 4. Architecture

| Unit | Kind | Responsibility |
|------|------|----------------|
| `src/moonface/signal/engine/audit.py` | new module | All audit analyses (LOO, conditional ordering, fitters, classification, verdicts). Imports panel machinery from `calibration.py`. |
| `src/moonface/signal/engine/calibration.py` | minimal edit | `scoring_pass(..., deriv_by_index: dict[int, DerivSnapshot] | None = None)` — passed into the two `book.score()` calls. Default `None` preserves current behavior exactly. No other change. |
| `tools/engine_audit.py` | new CLI | `--stage 1|2`, span/warmup flags mirroring `tools/engine_calibration.py`, writes `experiments/engine/audit_report_stage{N}.json`. |
| `src/moonface/signal/engine/deriv_history.py` | new module (Stage 2) | Reconstructs per-bar `DerivSnapshot`s historically. |
| `experiments/engine/SCORING_AUDIT_2026-07.md` | pre-reg doc | Frozen criteria per stage; results and verdict written once per stage. |

Reused from `calibration.py` (unmodified semantics): `scoring_pass`,
`overlapping_panel`, `simulate_entry`, `spearman`,
`block_bootstrap_rho_ci`, `bucket_stats`, `series_fingerprint`, and the
frozen analysis constants (block 168 bars, 1000 draws, seed, floors). Panel
semantics stay bit-identical to the 2026-07 baseline so results are
one-to-one comparable.

### Data flow

1. Load cached 1h candles (same span as the calibration run: 2020-01 →
   2026-06, warmup 6000) → fingerprint recorded.
2. (Stage 2) `deriv_history` builds `deriv_by_index`.
3. `scoring_pass` produces per-bar `BarRow`s (signed module points, book
   states, decisions).
4. `overlapping_panel` per book → `HypoTrade` panel (frozen entry/exit
   discipline, extreme-vol excluded, incompletes counted).
5. `audit.py` computes analyses §5, writes one JSON report per stage.
6. Human transcribes verdict into the pre-reg doc's results section.

## 5. Analyses (per book × direction, plus pooled per book)

1. **Baseline ordering under current weights.** Spearman ρ(score, net R)
   with block-bootstrap CI — including per-direction ρ (the 2026-07 report
   gave per-direction mean R only, not ordering).
2. **Leave-one-out (LOO) marginal contribution.** For each module *m*:
   recompute the book score without *m* on the same bars, panel membership
   held fixed; Δρ = ρ(LOO) − ρ(baseline) with block-bootstrap CI (paired,
   same blocks/draws/seed). Bars where dropping *m* flips or zeroes the book
   direction are counted and excluded from that module's Δρ (isolates
   ordering contribution from entry-selection change; exclusion counts
   reported).
3. **Single-module conditional ordering.** ρ(module signed points, net R)
   within the panel — trade-outcome-based, unlike the existing fixed-horizon
   IC table (which stays SECONDARY).
4. **Fitted upper bound.** Chronological split at the bar 60% through the
   scored span: train = trades that both enter AND exit before the boundary;
   test = trades entering at or after boundary + 168 bars (purge gap).
   Trades straddling the boundary or entering inside the gap are dropped
   (counts reported). Fitters (pre-enumerated, both always reported, no
   selection between them):
   - F1: NNLS (nonnegative least squares) of net R on module signed points;
   - F2: logistic regression of win (net R > 0) on module signed points,
     coefficients clamped nonnegative.
   Constraint: nonnegative weights, sum-normalized to 100. Verdict metric:
   OOS Spearman of fitted score vs net R with block-bootstrap CI, alongside
   the current weights' OOS ρ on the identical test window.
5. **Per-module classification** (from LOO Δρ):
   - CONTRIBUTES — removal hurts ordering, CI-clean (Δρ CI entirely < 0);
   - DEAD — Δρ CI spans 0;
   - HARMFUL — removal improves ordering, CI-clean (Δρ CI entirely > 0).
   Power floors as in the calibration diagnostic (≥ 200 panel events per
   split); any split below floor reports UNDERPOWERED instead of a class.

## 6. Stage 2 data path (`deriv_history.py`)

- `funding_pct`: historical funding rates via the already-cached
  `moonface.research.universe_data.fetch_funding_rates`, reproducing the
  live `deriv.py` percentile-of-last semantics exactly (same trailing
  window).
- `oi_change_6h`: Binance Vision free 5-min open-interest metrics (coverage
  since 2020-09, which matches the first scored bar of the baseline run
  anyway). Resampled so each 1h bar's snapshot uses only data available at
  that bar's close; `oi_change_6h` computed from the 5-min points with the
  same formula as live `_oi_change_from_points`.
- Downloads cached under `.backtest_cache`; loader is deterministic given
  the cache.
- **Integrity gate (frozen in pre-reg before Stage 2):** per-field coverage
  over the scored span must meet a frozen floor; gaps are journaled in the
  report; below-floor coverage → CLI exits non-zero and Stage 2 does not
  run to verdict. Missing per-bar values degrade exactly as the live engine
  does (module returns "unavailable", 0 points, `data_ok` False) — never
  imputed.

## 7. Verdicts (per book; exact numeric definitions frozen in pre-reg)

Evaluated in this order (first match wins — the three are mutually
exclusive by construction):

1. **NO_SIGNAL_IN_ANY_WEIGHTING** — neither any fitter nor the current
   weights achieve CI-clean positive OOS ρ. The modules themselves lack
   signal; weights are exonerated.
2. **CURRENT_WEIGHTS_ADEQUATE** — the current weights achieve CI-clean
   positive OOS ordering on the test window. (If a fitter's CI additionally
   sits entirely above the current point estimate, that is REPORTED as
   headroom, not a verdict change.)
3. **WEIGHTS_MISCALIBRATED** — otherwise: at least one fitter is CI-clean
   positive OOS while the current weights are not. Weights are a real
   suspect for the weak signal quality.

Plus the per-direction evidence table (baseline ρ, LOO classes, fitted OOS ρ
for LONG vs SHORT separately) as the SHORT-decision input. Explicit
non-action: no constant change flows from this audit; any v2.2 is a separate
human decision with a new registration.

## 8. Error handling

- Deterministic seeds everywhere (bootstrap seed shared with calibration).
- Series fingerprint + engine hash recorded in every report JSON.
- CLI exits non-zero only on mechanical failure: truncated candle data, or
  Stage-2 deriv coverage below the frozen floor. Power shortfalls never
  abort — a pooled book panel below floor reports verdict UNDERPOWERED
  (calibration-diagnostic convention); per-direction splits below floor
  report UNDERPOWERED in place of a classification.
- No network access at analysis time beyond the cached loaders' own
  download-if-missing step; tests are fully hermetic.

## 9. Testing

- LOO recompute on synthetic book scores (hand-computable Δ).
- Fitters on synthetic data: known-ordering case recovers CI-clean positive
  OOS ρ; pure-noise case yields CI spanning 0.
- Purge-gap/split logic: no train/test overlap within 168 bars.
- `deriv_history` resampler against a golden fixture (small synthetic 5-min
  series → expected per-bar snapshots; no lookahead).
- Regression: `scoring_pass` with default `deriv_by_index=None` produces
  byte-identical rows to the pre-change implementation.
- House conventions: pytest, hermetic, no live network in tests.

## 10. Out of scope

- Any change to engine constants, weights, thresholds, or the v2.1
  registration/clock.
- The "more signals / LONG+SHORT / more symbols" design itself — that
  brainstorm resumes after this audit's verdicts and is a separate spec.
- New historical calibration *of the frozen v2.1 hash* — the one-run rule
  stands; this audit's fitted weights, if ever adopted, define a v2.2
  candidate only.
