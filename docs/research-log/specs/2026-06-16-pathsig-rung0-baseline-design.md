# Path Signal Rung-0 Baseline — Design

- **Date:** 2026-06-16
- **Status:** Design approved; implementation plan pending
- **Program:** BTC Distributional Path Signal
  (`docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md`)
- **Builds on:** the rung-0 *plumbing* delivered by
  `docs/research-log/plans/2026-06-16-path-signal-foundations.md` (dataset, leak-proof
  HTF alignment, purged/embargoed walk-forward, cost model, WAIT-default policy,
  dual-frame evaluator) — all verified on **synthetic** data (603 tests).

## 0. Premise

The foundations proved the pipeline runs end-to-end on a synthetic bundle through a
trivial constant predictor. Nothing has yet touched the real cached data, and no real
number exists. This plan delivers the program's **rung 0**: replay the existing, already
screened signal families through the new harness on the real deploy asset (BTC), under
real costs, sizing, and the dual risk frame, on the *exact folds* rung 1 and rung 2 will
later use.

Rung 0 is the **floor**, not a hypothesis. Its job is twofold:
1. **Harness validation against known results.** The prior program's replicated finding —
   positive fixed-horizon drift, no bounded-risk path, structural drawdown wall — must
   reappear here. A signal that suddenly looks *great* through this harness is evidence of
   a harness bug, not a discovery.
2. **The attribution baseline.** Rung 1 (regime-weighted ensemble) and rung 2 (the
   distributional path model) must each beat this floor on identical folds. Without it, no
   later edge can be attributed to path-modeling rather than ensembling or capacity.

## 1. Objective & scope

Produce a per-signal, dual-frame **baseline table** for the ~16 already-screened signal
families, measured on BTCUSDT 4h through the pathsig harness over purged/embargoed
walk-forward folds, with the final 20% sealed as the lockbox tail (untouched by rung 0).

**In scope:** real-data loader for the BTC dataset (incl. cross-sectional ranks from the
16-asset pool), the rung-0 empirical-moment replay driver, a `baseline` CLI subcommand,
and tests. **Out of scope:** the rung-1 ensemble, any learned model, any lockbox opening,
any parameter tuning. (Rung-0 uses fixed, uniform policy constants across all signals.)

## 2. Signal set (frozen for this baseline)

Replayed exactly as defined in the existing screens, resolved through
`moonface.research.entries.generate_entries(family, params, bundle)`. Generators are
horizon-independent; the label horizon comes from the program freeze, **not** the
original screens' horizons.

**Price family** (`tools/drift_screen.py`):
- `donchian_break` `{n:100}`, `donchian_break` `{n:55}`
- `atr_channel_break` `{k:1.5, atr_period:14}`, `atr_channel_break` `{k:2.0, atr_period:14}`
- `ma_cross` `{fast:50, slow:200}`, `roc_sign` `{period:24}`, `price_vs_ma` `{period:100}`

**Funding / positioning / orderbook** (`tools/drift_screen_multifamily.py`):
- `funding_fade` `{window:60, z_thr:1.5}`, `funding_confirm` `{persist:6, lvl:0.0003}`,
  `funding_flip` `{debounce:6}`
- `oi_build_momentum` `{window:180, lookback:6, z_thr:1.5}`,
  `oi_flush_reversal` `{window:180, lookback:6, z_thr:1.5}`,
  `toptrader_follow` `{window:180, z_thr:1.5}`,
  `taker_flow_momentum` `{window:180, z_thr:1.5}`
- `ob_imbalance_follow` `{window:180, z_thr:1.5}`, `ob_imbalance_follow` `{window:180, z_thr:2.0}`

16 signal/param combos total. The positioning families need the matching `feature`
metrics field on BTC's bundle (`sum_open_interest` for OI families,
`sum_toptrader_long_short_ratio` for toptrader, `sum_taker_long_short_vol_ratio` for
taker); `ob_imbalance_follow` needs `bookdepth`. A signal whose BTC bundle lacks its
required series is reported as `no_data` and skipped (not silently zeroed).

**Horizons.** Replay at the program-frozen `h ∈ {6, 12}` (primary `h=6`). `h=6` is the
binding baseline; `h=12` is reported alongside. (The original screens used `h=24`/`h=6`;
the program freeze governs here so every rung shares one label definition.)

## 3. Architecture

Two new pure-consumer modules in the existing subpackage plus one CLI subcommand. No
frozen interface (`FEATURE_NAMES`, `Sample`, `Distribution`, `Decision`, `decide`,
`evaluate_strategy`, `walk_forward_folds`) is modified.

```
real cached CSVs ──┐
                   ▼
  pathsig/data.py : build_btc_dataset(...)
    • BTC 4h candles + funding + OI/positioning metrics + bookdepth (injectable readers)
    • BTC 1d / 1w derived by closed-bar resampling of the 4h series  (HTF block)
    • 16-asset pool 4h candles+funding → BTC cross-sectional ranks
    └─► build_dataset(bundle, h, atr_period, xs_ret_rank, xs_funding_rank,
                      d1_candles, w1_candles)  →  list[Sample]      (existing, unchanged)
                   ▼
  walk_forward_folds(len(samples), n_folds, embargo=h, lockbox=0.2)  (existing)
                   ▼
  pathsig/baseline.py : replay_signal(family, params, btc_bundle, samples, folds, h, ...)
    • build fire-map  candle_index → side   via generate_entries(family, params, bundle)
    • per fold: fit empirical Distribution from TRAIN-fold fired samples' labels
    • emit decisions on TEST-fold fired samples → decide() → collect
    • evaluate_strategy(decisions, labels, atr_fracs, fundings, ...) → dual-frame result
                   ▼
  tools/path_signal.py  `baseline` subcommand → JSON table (one row per signal × horizon)
```

## 4. `pathsig/data.py` — real-data loader

`build_btc_dataset(readers, h, atr_period, pool_symbols, *, n=None) -> tuple[DataBundle, list[Sample]]`

- **Readers are injectable** (same pattern as `multifamily_loader.default_readers`): a dict
  of `candles/funding/metrics/bookdepth` callables. Tests pass synthetic readers; the
  default wires the existing CSV caches over `.backtest_cache`. No network or disk in tests.
- **BTC bundle:** `candles = read("BTCUSDT","4h")`, `funding`, `feature` (the metrics field
  required by the positioning families — loaded per family at replay time, see §5 note),
  `bookdepth`. Returned so `baseline.py` can run `generate_entries` against it.
- **HTF:** derive `d1_candles` / `w1_candles` by **closed-bar resampling** of the BTC 4h
  series (6 bars → 1 day, 42 → 1 week), aggregating open/high/low/close/volume over
  completed groups only. Avoids a separate cached-series dependency and is leak-safe (a
  resampled bar's timestamp is its open; `align_htf_index` already gates on close time).
- **Cross-sectional ranks:** load the 16-asset pool's 4h candles + funding, align to BTC's
  timestamp grid, and at each BTC bar compute BTC's **percentile rank** of trailing return
  and of funding level within the set of pool assets that have data at-or-before that bar.
  Point-in-time only (assets missing at a bar are excluded from that bar's ranking; a bar
  with zero pool peers ranks `0.5` by convention so the feature is never `None` for a
  price-complete bar). Yields the `xs_ret_rank` / `xs_funding_rank` series `build_dataset`
  consumes.
- **Output:** the BTC `DataBundle` and the `list[Sample]` from `build_dataset`. Because the
  16 frozen features include OI z-score and HTF blocks, feature-incomplete bars (early
  warmup, sparse OI) are dropped by `build_dataset` — so the Sample grid is smaller than the
  original screens' event sets. This is intended: rung 1/2 face the same grid, so the
  baseline must too.

## 5. `pathsig/baseline.py` — empirical-moment replay

`replay_signal(family, params, bundle, samples, folds, h, *, edge_threshold,
kelly_scale, max_fraction, taker_bps, slippage_bps, n_trials) -> dict`

- **Fire-map.** `events = generate_entries(family, params, bundle)` → `{candle_index: side}`.
  Serial overlap is **not** pre-dropped here (the embargo + per-bar decision handle
  horizon overlap); each fired bar that survives as a `Sample` is a candidate.
- **Per-fold empirical fit (the only rung-0 "learning").** For a fold, over `train_idx`
  samples whose `Sample.index` is in the fire-map, read the stored label
  `(ret_r, mae_r, mfe_r)`, **mirror to the signal's own direction** when `side == "SHORT"`
  (`ret→-ret`, and swap+negate so `mae≤0`, `mfe≥0`), then average:
  - `p_up` = fraction with mirrored `ret_r > 0`
  - `exp_ret_r`, `exp_mae_r` (≤0), `exp_mfe_r` (≥0) = means.
  This `Distribution` is frozen for the fold. **Leak-free:** test labels never enter the
  fit; the embargo purges horizon overlap across the train/test boundary; the lockbox tail
  is excluded by `walk_forward_folds`. A fold with too few train events (`< MIN_FIT_EVENTS`,
  e.g. 10) emits no decisions for that fold (recorded as skipped).
- **Test decisions.** For each `test_idx` sample that fired, call
  `decide(distribution, edge_threshold, kelly_scale, max_fraction)`. `decide` re-derives
  LONG/SHORT from the edge sign — reproducing the signal's direction when the empirical
  edge clears threshold, and **downgrading to WAIT when drift-per-unit-MAE is too small**.
  That WAIT-downgrade is itself an honest rung-0 outcome. Non-fired test bars are implicit
  WAIT (no decision emitted).
- **Evaluation.** Concatenate decisions/labels/atr_fracs/fundings across folds (atr_frac is
  `Sample.x[FEATURE_NAMES.index("atr_frac")]`; funding from the BTC bundle at the sample's
  index), then `evaluate_strategy(..., drawdown_cap_r=15.0)`. Returns both
  `risk_adjusted` (Sharpe/MAR/DSR) and `fixed_cap` (total_r, max_drawdown_r, within_cap).
- **Uniform policy constants** across all 16 signals (no per-signal tuning — that is rung 2's
  job): `edge_threshold`, `kelly_scale`, `max_fraction`, `taker_bps`, `slippage_bps` are
  module constants, surfaced in the CLI output for the record. `n_trials` for DSR deflation
  at rung 0 = the number of signals × horizons evaluated in this baseline pass.

*Metrics-field note:* positioning families each need a different `feature` series, so
`replay_signal` (or the CLI driver) loads the BTC bundle with the family's required
`metrics_field`/`bookdepth` before calling `generate_entries`; the **feature-vector**
construction for the Sample grid uses the program-frozen OI field (`sum_open_interest`) so
the Sample grid stays identical across signals. The signal's own data and the Sample grid's
features are separate concerns — only the latter must be fold-identical.

## 6. CLI & output

`tools/path_signal.py` gains a `baseline` subcommand:

```
python tools/path_signal.py baseline --out experiments/path_signal/rung0_baseline.json \
    [--cache-dir .backtest_cache] [--n-folds 5] [--horizons 6 12]
```

Writes a JSON document: the run config (policy constants, folds, horizons, lockbox
fraction, n_trials, sample count, lockbox boundary) and one row per signal × horizon with
`{family, params, h, status, n_events, n_trades, risk_adjusted{...}, fixed_cap{...}}`.
`status ∈ {ok, no_data, too_few_events}`. Sorted by `fixed_cap.total_r` descending for
quick eyeballing. Also prints a compact table to stdout.

## 7. Leakage & bias controls (explicit)

- **Point-in-time features:** unchanged frozen builders; HTF via close-time-gated
  `align_htf_index`; xs ranks computed only from pool data at-or-before each bar.
- **Purge + embargo:** `embargo = h` (the label horizon) on each side of every test block.
- **Per-fold fit:** empirical moments use train-fold labels only; never test, never lockbox.
- **Lockbox untouched:** `walk_forward_folds(lockbox_fraction=0.2)` never returns the tail;
  rung 0 does not open it (an explicit non-goal — opening is a rung-2 step).
- **Costs on the sized strategy:** taker + slippage + funding via the existing `apply_costs`,
  exactly as rung 1/2 will apply them.

## 8. Testing strategy (TDD, flat per repo convention)

- `tests/test_pathsig_data.py`: synthetic injectable readers → `build_btc_dataset` returns a
  non-empty Sample grid with complete vectors; resampled d1/w1 have correct bar counts and
  closed-bar OHLC; xs ranks are in [0,1] and point-in-time (a future-only asset never
  affects an earlier bar's rank); a bar with no pool peers still ranks (degenerate → 0.5 or
  defined convention).
- `tests/test_pathsig_baseline.py`: with a hand-built bundle + a stub signal that fires on
  known bars and a known label pattern: (a) the per-fold empirical Distribution equals the
  manual train-fold mean; (b) SHORT mirroring flips sign and keeps `mae≤0/mfe≥0`; (c) a
  too-few-train-events fold emits no decisions; (d) a positive-drift / large-MAE stub
  reproduces the expected WAIT-or-breach behaviour (the wall), not a passing edge; (e)
  leak guard: shifting a *test-fold* label does not change the fitted distribution.
- `tests/test_pathsig_baseline_cli.py`: `baseline --out` on a tiny synthetic cache writes
  valid JSON with the documented schema and `status` values; exit 0.
- Full suite + `ruff check` over the new modules and the CLI stay green.

## 9. Interpretation criteria (rung 0 is descriptive, not a gate)

Rung 0 has **no pass/fail gate** — it sets the floor and validates the harness. Expected
and healthy: positive `exp_ret_r` on drift-bearing signals (e.g. `funding_fade`,
`donchian_break`) paired with large `|exp_mae_r|`, producing either WAIT-downgrades or
`within_cap = false` fixed-cap breaches — the structural wall, reproduced. **Red flags to
investigate before trusting the harness:** any signal clearing the −15R cap with a high DSR,
or DSR/MAR wildly inconsistent with the prior program's per-family findings. The output is
recorded to `experiments/path_signal/rung0_baseline.json` as the attribution baseline; the
best `fixed_cap.total_r` (and best `risk_adjusted`) become the numbers rung 1 must beat.

## 10. Out of scope

- Rung 1 ensemble, rung 2 model, rung 3 sequence model — separate follow-on plans.
- Opening the lockbox tail — a rung-2 step.
- Per-signal parameter tuning — uniform constants only at rung 0.
- New data sources — deferred behind a clean kill of the whole program.

## 11. File structure

- Create: `src/moonface/research/pathsig/data.py` — `build_btc_dataset`, resampling +
  cross-sectional rank helpers.
- Create: `src/moonface/research/pathsig/baseline.py` — `replay_signal`, fold empirical fit,
  `run_baseline` driver, the frozen 16-signal list + policy constants.
- Modify: `tools/path_signal.py` — add the `baseline` subcommand.
- Create: `tests/test_pathsig_data.py`, `tests/test_pathsig_baseline.py`,
  `tests/test_pathsig_baseline_cli.py`.
- Generated (force-add, gitignore convention): `experiments/path_signal/rung0_baseline.json`.
