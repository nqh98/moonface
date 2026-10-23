# Reconciliation — Donchian 4h: edge-search NEGATIVE vs deployable / revalidation

## Why the two records do not conflict

The Stage-1 pre-screen in this directory's RESULT.md killed `donchian_break_n40` (gross
Stouffer Z = 1.101 < 2.0, n=60). That probe measures GROSS directional drift at a FIXED
HORIZON (h=12 bars, `research/edge_search.py:prescreen` → `event_outcome`); it never invokes
a trailing exit. It refutes fixed-horizon drift ON ITS FROZEN 2-YEAR WINDOW ONLY (the
edge-search swing-4h window is 2024-06-12 → 2026-06-12, 4380 bars).

The deployed Donchian strategy is EXIT-DRIVEN trend-following (ATR initial stop + Donchian
trailing stop, `research/trend_sim.py:simulate_donchian`). It PASSED the deployable
walk-forward to PAPER (`experiments/deployable/DONCHIAN_SLICE2_RESULT.md`: PF 1.75,
expectancy 0.44R, MAR 4.68, maxDD -7.79R, robust_frac 0.79 on overlapping windows). The edge
lives in the asymmetry of the exit, not in fixed-horizon drift — so the two records do not
conflict.

The 2026-06-20 revalidation (`experiments/deployable/DONCHIAN_REVALIDATION_RESULT.md`)
CONFIRMS the exit-driven edge directly via its exit ablation (same Donchian-40 entries,
three exits): trail expectancy 0.65R / MAR 5.83 materially dominates the costed
fixed-horizon exit (expectancy 0.10R / MAR 1.49) and stop-only. The gross fixed-horizon
probe is report-only and gates nothing.

## One nuance: the gross-drift picture is window-dependent

The edge-search Stage-1 window was 2024-06-12 → 2026-06-12 (4380 bars); on that 2-year
window `donchian_break_n40` gross z = 1.101. The revalidation runs the SAME gross probe over
the full 2020-01-01 → 2026-06-20 window (14175 bars) and reads z = 2.45 — above the 2.0
floor. The longer window (notably the 2020–2023 regime) contributes positive-drift breakouts
the 2-year edge-search window did not cover. This does not change the deployed edge, which is
the trailing exit (net ablation above).

## Verdict from the revalidation: INCONCLUSIVE / PAPER-SUSPENDED

All STRUCTURAL gates pass: non-overlap walk-forward aggregate ECON_BAR (PF 1.75 /
expectancy 0.44R / MAR 4.68 / maxDD -7.79R, wf_pass=True), base-cost econ_pass=True, exit
ablation dominance, no single-trade outlier dependence (top1 contribution 33%,
td_extreme=False), not bull-concentrated (rg_flag=False; both bull and bear regimes
positive). The single nonstructural miss is robust_frac 0.5 < 0.60 on the strict N=4
NON-OVERLAPPING yearly windows — a quantization artifact (Slice-2's overlapping-window
robust_frac 0.79 is the finer read). The strategy is therefore neither reaffirmed nor
downgraded: it remains active paper, suspended pending the finer robustness read.

## Frozen artifacts

The edge-search PREREGISTRATION.md and RESULT.md remain frozen and correct for what they
tested (2-year window, gross fixed-horizon drift). Paper-only — not live capital.
