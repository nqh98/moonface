# v2 Scoring Component & Weight Audit (2026-07)

**STATUS: COMPLETE (2026-07-05). Stage-1 and Stage-2 results published;
criteria unchanged since their respective pre-run freezes. Verdicts:
Stage 1 (price core) trend CURRENT_WEIGHTS_ADEQUATE, mean_revert
NO_SIGNAL_IN_ANY_WEIGHTING; Stage 2 (deriv-inclusive) both books
NO_SIGNAL_IN_ANY_WEIGHTING.**

Spec: `docs/research-log/specs/2026-07-05-scoring-audit-design.md`
Tooling: `src/moonface/signal/engine/audit.py`, `tools/engine_audit.py`
Engine identity: frozen v2.1 hash
`4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a`.
This lane is READ-ONLY: no frozen constant, config, journal, or
registration text is touched; the forward-paper clock is unaffected.
Findings feed a separate human-gated v2.2 / expansion decision only.

## The two questions

Per book and per direction: (a) does each module contribute
outcome-ordering signal; (b) could any nonnegative reweighting achieve
out-of-sample ordering - i.e. are the hand-set weights the problem, or the
modules themselves?

## Stage 1 - registered run (frozen)

- Command: `.venv/bin/python -m tools.engine_audit --stage 1 --start-ms
  1577836800000 --end-ms 1782316800000 --warmup 6000 --out
  experiments/engine/audit_report_stage1.json`
- Data: cached `BTC/USDT:USDT` 1h perp (`.backtest_cache`), 2020-01 to
  2026-06 - the calibration diagnostic's exact span; series fingerprint is
  recorded in the report JSON.
- One run. Re-runs only for mechanical failure (non-zero exit, truncated
  data), never to revisit a completed result.

## Stage 1 - frozen criteria

Panel semantics are identical to `CALIBRATION_DIAGNOSTIC_2026-07.md`
(overlapping panel, frozen exit discipline, extreme-vol excluded).
Inference: moving-block bootstrap, block 168 bars, 1000 draws, seed
20260704; power floor 200 events per split (below floor = UNDERPOWERED, no
classification).

- **Per-module class, per split (pooled/LONG/SHORT) - LOO Δρ = ρ without
  module - ρ with, paired bootstrap, direction-changed bars excluded and
  counted:** CONTRIBUTES = Δρ CI entirely < 0; HARMFUL = CI entirely > 0;
  DEAD = CI spans 0.
- **Fitted upper bound:** chronological split at the bar 60% through the
  scored span; train trades exit before the boundary; test trades enter >=
  boundary + 168 bars; straddlers/gap entries dropped and counted. Fitters
  (both reported, none selected): NNLS of net R on direction-aligned
  standardized module points; nonnegative-clamped logistic of win. Weights
  sum-normalized to 100 (all-zero = degenerate, cannot pass). Verdict
  metric: OOS Spearman(fitted score, net R), block-bootstrap 95% CI, on
  the pooled test panel.
- **Book verdict (first match):** UNDERPOWERED (train or test below floor);
  NO_SIGNAL_IN_ANY_WEIGHTING (neither any fitter nor the current weights
  CI-clean positive OOS); CURRENT_WEIGHTS_ADEQUATE (current weights
  CI-clean positive OOS; fitter headroom reported, never verdict-changing);
  WEIGHTS_MISCALIBRATED (otherwise).
- **Reported, never gated:** per-direction baseline/conditional/OOS tables
  (the SHORT-decision evidence), LOO exclusion counts, split drop counts.

## Stage 1 assumptions

1. deriv=None: Stage 1 covers the PRICE-STRUCTURE core only (trend book
   caps at 85/100; revert book lacks m4_fund_ct and m5_oi_flush). The three
   deriv modules report as all-zero columns (rho None) - expected, not
   findings.
2. Sub-threshold hypothetical trades are counterfactual, as in the
   calibration diagnostic; they measure ordering, not tradability.
3. Fitted weights are on STANDARDIZED features - not directly comparable to
   the engine's point weights; only the OOS ordering they achieve is
   verdict-bearing.

## What this audit can and cannot conclude

It can attribute weak score quality to weights vs modules, and provide
per-direction evidence for a future SHORT decision. It cannot validate an
edge, recommend constant changes, or trigger any engine action. Any v2.2
is a separate human decision (new ENGINE_VERSION -> hash -> registration).

## Stage 1 - results (write once, after the registered run)

**Run provenance.** First execution (2026-07-05 04:25, exit 0) was
invalidated by a mechanical failure: `loo_analysis` carried an unregistered
`|Δρ| < 0.1 -> DEAD` short-circuit absent from the frozen criteria above
(classes are CI-position only). Fixed in commit f65200c; corrected
registered run executed 2026-07-05 06:25, exit 0, same command. The
bootstrap is seeded: the corrected report is identical to the invalidated
one in every number and differs only in LOO class labels (verified by
field-level diff). Report: `audit_report_stage1.json`, engine hash
`4e35561f...`, fingerprint `fedf68d4...`, 56800 candles, 50800 scored bars.

### trend book - verdict: CURRENT_WEIGHTS_ADEQUATE

Panel: 46529 events (31 incomplete, 402 extreme-vol skipped).

Baseline ordering rho(score, net R), CI 95:

| split | n | rho | CI |
|---|---|---|---|
| pooled | 46529 | 0.0520 | [0.0223, 0.0805] |
| LONG | 26933 | 0.0505 | [0.0069, 0.0882] |
| SHORT | 19596 | 0.0539 | [0.0016, 0.1045] |

LOO classes (pooled / LONG / SHORT), pooled Δρ CI, direction-changed bars:

| module | classes | pooled Δρ CI | dir-changed |
|---|---|---|---|
| m1_macro | DEAD / DEAD / DEAD | [-0.0428, 0.0494] | 13977 |
| m2_breakout | CONTRIBUTES / CONTRIBUTES / DEAD | [-0.0082, -0.0010] | 622 |
| m2_ma_align | DEAD / DEAD / DEAD | [-0.0333, 0.0131] | 4534 |
| m3_roc | CONTRIBUTES / CONTRIBUTES / CONTRIBUTES | [-0.0440, -0.0128] | 2713 |
| m4_pullback | HARMFUL / DEAD / HARMFUL | [0.0003, 0.0222] | 3573 |
| m5_funding | DEAD / DEAD / DEAD (all-zero column, Stage-1 expected) | [0, 0] | 0 |

Conditional ordering highlights (direction-aligned points vs net R):
m3_roc pooled 0.0838 [0.0532, 0.1124], SHORT 0.1129 [0.0653, 0.1598];
m2_breakout pooled 0.0400 [0.0205, 0.0577] (clean positive both
directions); m4_pullback SHORT -0.0483 [-0.0809, -0.0132] (clean
negative); m1_macro and m2_ma_align span 0 in all splits; m5_funding rho
None (constant column).

Fitted upper bound: boundary 36480, train 28091, test 18263, dropped 175.
OOS pooled rho(score, net R), CI 95:

| weighting | rho | CI | CI-clean |
|---|---|---|---|
| current (frozen) | 0.0603 | [0.0094, 0.1048] | yes |
| nnls_net_r | 0.0495 | [-0.0029, 0.0940] | no |
| logistic_win | 0.0508 | [-0.0020, 0.0949] | no |

Per direction, current weights: LONG 0.0665 [-0.0063, 0.1298], SHORT
0.0533 [-0.0350, 0.1274] - neither clean on its own. Fitter weights
(standardized-feature scale, reported never selected): nnls m2_breakout
85.54 / m1_macro 14.13 / m3_roc 0.33; logistic m1_macro 42.25 /
m2_breakout 33.24 / m3_roc 24.51; both zero m2_ma_align, m4_pullback,
m5_funding. Neither fitter is degenerate.

### mean_revert book - verdict: NO_SIGNAL_IN_ANY_WEIGHTING

Panel: 31801 events (3 incomplete, 266 extreme-vol skipped).

Baseline ordering: pooled -0.0029 [-0.0237, 0.0178] (n 31801); LONG 0.0175
[-0.0133, 0.0482] (n 14974); SHORT -0.0214 [-0.0502, 0.0070] (n 16827).
All spans include 0.

LOO: every module DEAD in every split (all Δρ CIs span 0; m4_fund_ct and
m5_oi_flush are all-zero Stage-1 columns). Direction-changed counts:
m1_sweep 2740, m2_reclaim 568, m3_divergence 4678, m6_stretch 11378,
deriv modules 0.

Conditional ordering: no module clean in any split; deriv columns rho None.

Fitted upper bound: boundary 36480, train 18509, test 13189, dropped 103.
OOS pooled: current -0.0085 [-0.0390, 0.0223]; nnls_net_r -0.0132
[-0.0470, 0.0204]; logistic_win -0.0076 [-0.0390, 0.0233]. Nothing
CI-clean positive in any split; neither fitter degenerate.

## Stage 2 - deriv-inclusive registered run (CRITERIA FROZEN pre-run)

- Command: `.venv/bin/python -m tools.engine_audit --stage 2
  --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000
  --coverage-floor 0.90
  --out experiments/engine/audit_report_stage2.json`
- Integrity gate: funding AND OI coverage >= 0.90 of scored bars, else exit
  non-zero, no verdict; coverage numbers publish in the report either way.
- Historical deriv semantics: per-bar snapshot at bar close (open + 1h);
  funding percentile over trailing 30 days inclusive of close; OI 6h change
  from Binance Vision 5-min sum_open_interest via the live formula. The
  5-min-vs-1h grid difference from live is accepted and documented.
- Criteria: IDENTICAL to Stage 1 (same panel, floors, classes, fitters,
  verdict precedence), now over all 12 modules with real deriv columns.
- One run. Re-runs only for mechanical failure. This section was frozen
  after Stage-1 results published and before any deriv data was fetched or
  inspected (Stage-1 facts cited: 50800 scored bars; trend
  CURRENT_WEIGHTS_ADEQUATE; mean_revert NO_SIGNAL_IN_ANY_WEIGHTING).

## Stage 2 - results (write once, after the registered run)

Registered run executed 2026-07-05 07:34, exit 0, one run. Report:
`audit_report_stage2.json`; engine hash `4e35561f...` and series
fingerprint `fedf68d4...` identical to Stage 1; 56800 candles, 50800
scored bars.

Deriv coverage (integrity gate 0.90): funding 1.0000, OI 0.9977 - PASS.
Archive symbol BTCUSDT. Panels differ from Stage 1 because real deriv
columns change scores and hence panel membership (trend 47598 vs 46529
events; mean_revert 37768 vs 31801).

### trend book - verdict: NO_SIGNAL_IN_ANY_WEIGHTING

Panel: 47598 events (31 incomplete, 418 extreme-vol skipped).

Baseline ordering: pooled 0.0507 [0.0206, 0.0800] (n 47598); LONG 0.0331
[-0.0101, 0.0715] (n 26186); SHORT 0.0718 [0.0254, 0.1188] (n 21412).

LOO classes (pooled / LONG / SHORT), pooled Δρ CI, direction-changed bars:

| module | classes | pooled Δρ CI | dir-changed |
|---|---|---|---|
| m1_macro | DEAD / DEAD / DEAD | [-0.0525, 0.0418] | 14616 |
| m2_breakout | CONTRIBUTES / DEAD / DEAD | [-0.0094, -0.0012] | 530 |
| m2_ma_align | DEAD / DEAD / DEAD | [-0.0298, 0.0149] | 4743 |
| m3_roc | CONTRIBUTES / DEAD / CONTRIBUTES | [-0.0420, -0.0090] | 3231 |
| m4_pullback | HARMFUL / DEAD / HARMFUL | [0.0052, 0.0245] | 2666 |
| m5_funding | DEAD / DEAD / DEAD | [-0.0226, 0.0161] | 4613 |

Conditional ordering: m3_roc pooled 0.0781 [0.0483, 0.1050], SHORT 0.1087
[0.0636, 0.1517]; m2_breakout pooled 0.0391 [0.0200, 0.0566] (clean both
directions); m4_pullback SHORT -0.0374 [-0.0699, -0.0053] (clean
negative); m5_funding spans 0 in all splits (pooled 0.0046
[-0.0262, 0.0384]); m1_macro and m2_ma_align span 0 in all splits.

Fitted upper bound: boundary 36480, train 28548, test 18880, dropped 170.
OOS pooled rho, CI 95:

| weighting | rho | CI | CI-clean |
|---|---|---|---|
| current (frozen) | 0.0326 | [-0.0138, 0.0748] | no |
| nnls_net_r | 0.0320 | [-0.0166, 0.0745] | no |
| logistic_win | 0.0258 | [-0.0223, 0.0676] | no |

Per direction, current weights: LONG 0.0182 [-0.0431, 0.0743], SHORT
0.0510 [-0.0278, 0.1231]. Fitter weights (standardized scale, reported
never selected): nnls m5_funding 42.28 / m2_breakout 22.30 / m3_roc 18.40
/ m1_macro 12.24 / m2_ma_align 4.77 / m4_pullback 0; logistic m5_funding
31.46 / m1_macro 28.09 / m3_roc 22.69 / m2_breakout 12.23 / m2_ma_align
5.53 / m4_pullback 0. Neither degenerate. Nothing CI-clean positive in
any split or weighting.

### mean_revert book - verdict: NO_SIGNAL_IN_ANY_WEIGHTING

Panel: 37768 events (3 incomplete, 377 extreme-vol skipped).

Baseline ordering: pooled -0.0007 [-0.0220, 0.0199] (n 37768); LONG
0.0108 [-0.0195, 0.0426] (n 16081); SHORT -0.0089 [-0.0375, 0.0175]
(n 21687). All spans include 0.

LOO classes (pooled / LONG / SHORT), pooled Δρ CI, direction-changed bars:

| module | classes | pooled Δρ CI | dir-changed |
|---|---|---|---|
| m1_sweep | DEAD / DEAD / DEAD | [-0.0019, 0.0230] | 3134 |
| m2_reclaim | DEAD / DEAD / DEAD | [-0.0050, 0.0075] | 409 |
| m3_divergence | DEAD / DEAD / DEAD | [-0.0155, 0.0072] | 3944 |
| m4_fund_ct | CONTRIBUTES / DEAD / CONTRIBUTES | [-0.0304, -0.0037] | 7204 |
| m5_oi_flush | CONTRIBUTES / CONTRIBUTES / DEAD | [-0.0061, -0.0007] | 801 |
| m6_stretch | DEAD / DEAD / DEAD | [-0.0163, 0.0076] | 6757 |

Conditional ordering, deriv modules per direction: m4_fund_ct pooled
0.0329 [0.0074, 0.0600], LONG 0.0502 [0.0071, 0.0925], SHORT 0.0318
[-0.0023, 0.0683]; m5_oi_flush pooled 0.0444 [0.0292, 0.0589], LONG
0.0530 [0.0257, 0.0748], SHORT 0.0341 [0.0164, 0.0533]. Price modules:
m1_sweep pooled -0.0230 [-0.0446, -0.0013] (clean negative); m2_reclaim,
m3_divergence, m6_stretch span 0 in all splits.

Fitted upper bound: boundary 36480, train 22738, test 14883, dropped 147.
OOS pooled: current -0.0164 [-0.0467, 0.0159]; nnls_net_r 0.0120
[-0.0323, 0.0500]; logistic_win -0.0083 [-0.0385, 0.0242]. Nothing
CI-clean positive in any split or weighting; neither fitter degenerate.
Fitter weights: nnls m4_fund_ct 47.82 / m1_sweep 29.76 / m5_oi_flush
19.62; logistic m1_sweep 63.67 / m4_fund_ct 21.88 / m2_reclaim 7.22 /
m5_oi_flush 4.72; both zero m6_stretch.
