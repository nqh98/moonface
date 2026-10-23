# Signal Matrix — Slice-1b Forward Registration (FROZEN)

**Status:** pre-registered, pre-run. Corrects three instrument defects found in the Slice-1
run ([[signal-matrix-horizon-harvest]] / `MATRIX_SLICE1_RESULTS.md`). Read-only; promotion is
a human decision. **Sealed BTC year still UNSPENT** (Slice-1 Gate 1 failed → never opened).

**Code:** `src/moonface/research/matrix/evaluate.py` (+ `signal/matrix/` primitives,
`tools/matrix_evaluate.py`). **Supersedes** `MATRIX_SLICE1_REGISTRATION.md`.

## Why Slice-1b (three principled instrument corrections)

Slice-1 returned `CLOSED_NEGATIVE_VALIDATION` but the DD-cap test was unreliable:

1. **Per-segment governor (was: global-then-split).** Slice-1 governed the full
   2020→2026 stream with one global drawdown state, then split into windows — so validation
   inherited train's underwater state (throttle entered pinned near zero) and the throttle
   controlled *global* DD while the gate scored *per-window* DD. Slice-1b splits the panel
   into train/val/sealed FIRST (`segment_panel`), then governs **each segment
   independently** (DD state resets per window). Now the throttle's budget and the gate's
   per-window maxDD are the same curve, and validation starts with a fresh budget. Fit stays
   train-only; frozen params applied forward. Convention note: per-window reset matches how
   the v2.2 per-window baseline maxDD is computed — an evaluation choice, not live behavior.
2. **Retain zero-size trades (was: dropped).** Throttled-to-zero trades are kept as
   `net_r=0`, `atr_frac_eff=0` (`cost_stress` adds nothing when af≤0). n now reflects
   realized entries; the evaluated sample cannot self-collapse. Conservative for the gate —
   zeros dilute the mean toward 0, making CI-lower>0 harder.
3. **Recalibrated power floor (was: PANEL_FLOOR=200).** The matrix uses non-overlapping
   one-position streams (~66 entries/yr on 4h → ~100 in an 18mo validation window even
   ungoverned), so 200 was structurally unreachable. Floor set to `MIN_VAL_TRADES=40`; the
   deflated block-CI (which widens at small n) is the binding power control.

## Frozen constants (verbatim from `research/matrix/evaluate.py`)

- Splits: span_start `1577836800000`, train_end `1704067200000`,
  sealed_start `1751328000000`, span_end `1782316800000`; purge `168h` (`repair.PURGE_MS`).
- Assets: BTC (fit + validation + sealed), ETH + SOL (transfer only). Interval `4h`.
- Primaries (FIXED, no search): `momentum_breakout` (Donchian `entry_n=20, trail_n=10,
  atr_period=14, k_stop=2.0, long_only`, **fees off**, native trailing exit) and
  `funding_fade` (`window=60, z_thr=1.5`, fixed **horizon=48**, `k=2.0`).
- Governor grid (6): `target_vol ∈ {0.015,0.02,0.03}` × `size_max ∈ {1.0,2.0}`,
  `size_min=0.0`, `dd_budget = |baseline validation max_dd_r|`. `vol_lookback=100`.
- `govern_scope = per_segment_reset`; `retain_zero_size = True`; `MIN_VAL_TRADES = 40`.
- Multiple-comparisons: `EFFECTIVE_TRIALS = 6×2 = 12`; `FAMILY_ALPHA=0.05`;
  `CI_LO_Q = 0.05/12/2`. Block bootstrap `BLOCK_BARS=168`, `BOOTSTRAP_DRAWS=1000`,
  `BOOTSTRAP_SEED=20260704`. Cost: uniform `net_r_1x = gross_r − COST_FRACTION/atr_frac`,
  governor scales, cost path gets `atr_frac_eff = atr_frac/size`.
- Baselines (v2.2, from `v3_eval_2026-07.json` baseline_v22): validation maxDD **−11.6455**,
  sealed maxDD **−4.1142**.

## Gates (metric = per-segment governed net-R; maxDD on that governed curve)

- **Gate 1 (validation):** `n ≥ 40` AND `net_r_3x > 0` AND deflated block-CI lower `> 0`
  AND `|maxDD| ≤ 11.6455`.
- **Gate 2 (sealed BTC, one-shot):** `net_r_3x > 0` AND `|maxDD| ≤ 4.1142`.
- **Gate 3 (transfer ETH/SOL):** each leg `n ≥ 20` AND `net_r_3x > 0`.

Sealed opens **only** if Gate 1 passes.

## Stop rule (pre-committed)

**ONE new registered run. No re-tuning on this data.** PASS (all gates) → small-size
candidate (NOT proven edge; BTC 1-yr sealed low power) + Slice-2 (meta-labeled conviction).
CLOSED_NEGATIVE → the corrected instrument confirms the horizon-exit + governor cannot
harvest the known drift under the cap; falsifies the "harvest the known drift" thesis and
closes Slices 2–3. Sealed year spent iff Gate 1 passes.

## The run

```
.venv/bin/python tools/matrix_evaluate.py --interval 4h \
  --start-ms 1577836800000 --end-ms 1782316800000 \
  --baseline-val-dd -11.6455 --baseline-sealed-dd -4.1142 \
  --out experiments/engine/matrix_slice1b_2026-07.json
```
Verdict recorded in `experiments/engine/MATRIX_SLICE1B_RESULTS.md`.
