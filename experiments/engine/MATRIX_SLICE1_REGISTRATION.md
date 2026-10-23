# Signal Matrix — Slice-1 Forward Registration (FROZEN)

**Status:** pre-registered, pre-run. Read-only instrument; promotion is a human decision.
**Design:** `docs/research-log/specs/2026-07-06-signal-matrix-horizon-harvest-design.md`
**Plan:** `docs/research-log/plans/2026-07-06-signal-matrix-horizon-harvest-slice1.md`
**Code:** `src/moonface/signal/matrix/` (pure live-capable primitives: Signal, horizon,
governor) + `src/moonface/research/matrix/` (backtest instrument: primaries, evaluate) +
`tools/matrix_evaluate.py`. Split honors the import boundary: `signal` must not depend on
`research`, so research primitives are wired to the governor from the `research` layer.

## Hypothesis (H1)

Harvesting each already-replicated primary with the record-indicated exit
(`funding_fade` = fixed 48-bar horizon; `momentum_breakout` = native Donchian trailing
exit), then applying a shared volatility-targeted + drawdown-throttled **governor**, makes
the positive drift survive net-R > 0 at 3× cost with maxDD ≤ the v2.2 baseline — on frozen
validation and then sealed OOS. **The governor is the single novel lever; entries/exits are
pre-registered, not searched.**

## Frozen constants (verbatim from `matrix/evaluate.py`)

- Splits: span_start `1577836800000`, train_end `1704067200000`,
  sealed_start `1751328000000`, span_end `1782316800000`; purge `168h` (`repair.PURGE_MS`).
- Assets: BTC (fit + validation + sealed), ETH + SOL (transfer only). Interval `4h`.
- Primaries: `momentum_breakout` (Donchian `entry_n=20, trail_n=10, atr_period=14,
  k_stop=2.0, long_only=True`, **fees off** — uniform cost applied downstream) and
  `funding_fade` (`window=60, z_thr=1.5, horizon=48, k=2.0`).
- Governor grid (6 configs): `target_vol ∈ {0.015, 0.02, 0.03}` × `size_max ∈ {1.0, 2.0}`,
  `size_min=0.0`, `dd_budget = |baseline validation max_dd_r|`. `vol_lookback=100`.
- Multiple-comparisons: `EFFECTIVE_TRIALS = 6 × 2 = 12`; `FAMILY_ALPHA = 0.05`;
  `CI_LO_Q = 0.05/12/2`. Block bootstrap `BLOCK_BARS=168`, `BOOTSTRAP_DRAWS=1000`,
  `BOOTSTRAP_SEED=20260704`. `PANEL_FLOOR = 200`.
- Cost model (uniform): `net_r_1x = gross_r − COST_FRACTION/atr_frac`; the governor scales
  and the cost-stress path receives `atr_frac_eff = atr_frac/size` so k× cost scales with
  size. Horizon `H=48` and Donchian params contribute **zero** trials.

## Fitting (train only, then frozen)

`fit_governor` picks the grid config with the highest **train** governed net_r whose train
governed maxDD ≤ `dd_budget`; ties broken by lowest `size_max` (least leverage). Nothing
else is fitted.

## Gates

- **Gate 1 (validation):** `n ≥ 200` AND `net_r_3x > 0` AND deflated block-CI lower bound
  `> 0` AND `|maxDD| ≤ |v2.2 validation maxDD|`.
- **Gate 2 (sealed BTC, one-shot):** `net_r_3x > 0` AND `|maxDD| ≤ |v2.2 sealed maxDD|`.
- **Gate 3 (transfer ETH/SOL):** each leg `n ≥ 20` AND `net_r_3x > 0`.

Metric = **governed** (sized) net-R; maxDD measured on the governed equity curve. Sealed
window opens **only** if Gate 1 passes.

## Verdicts (`MATRIX_VERDICTS`)

`CLOSED_NEGATIVE_VALIDATION` → `CLOSED_NEGATIVE_SEALED_BTC` →
`CLOSED_NEGATIVE_TRANSFER` → `ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.

## Stop rule (pre-committed)

- **ONE registered run.** No re-tuning on this data (a second config = a new registration).
- **PASS** (all gates) → small-size candidate, NOT proven edge (BTC 1-yr sealed low power);
  proceed to Slice-2 (meta-labeled conviction). Promotion stays a human decision.
- **CLOSED_NEGATIVE** → the horizon exit + governor cannot harvest the known drift under the
  cap; this falsifies the "harvest the known drift" thesis (deeper than "the bracket was
  wrong") and closes Slices 2–3.

## The run (HUMAN-GATED — spends the sealed year iff Gate 1 passes)

1. Obtain v2.2 baseline validation/sealed `max_dd_r` (reuse `v3/evaluate.py::build_eval_report`
   `base_val`/`base_sealed`).
2. Run:
   ```
   .venv/bin/python tools/matrix_evaluate.py --interval 4h \
     --start-ms 1577836800000 --end-ms 1782316800000 \
     --baseline-val-dd <V22_VAL_DD> --baseline-sealed-dd <V22_SEALED_DD> \
     --out experiments/engine/matrix_slice1_2026-07.json
   ```
3. Record the verdict in `experiments/engine/MATRIX_SLICE1_RESULTS.md`.
