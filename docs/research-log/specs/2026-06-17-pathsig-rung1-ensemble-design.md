# Path Signal Rung-1 Regime-Weighted Ensemble — Design

- **Date:** 2026-06-17
- **Status:** Design approved; implementation plan pending
- **Program:** BTC Distributional Path Signal
  (`docs/research-log/specs/2026-06-16-btc-distributional-path-signal-design.md`)
- **Builds on:** rung-0 baseline
  (`docs/research-log/specs/2026-06-16-pathsig-rung0-baseline-design.md`,
  `docs/research-log/plans/2026-06-16-pathsig-rung0-baseline.md`) — its `data.py`
  (real BTC Sample grid), `baseline.py` (`fit_distribution`, `_mirror`, policy
  constants, `SIGNALS`), and the foundations harness (`decide`,
  `evaluate_strategy`, `walk_forward_folds`).

## 0. Premise

Rung 0 established the floor: the drawdown wall reproduced, **DSR 0.000 on all 30
scored signal rows**, the only cap-clean positive a borderline +24R/MAR-0.92
(`atr_channel_break` h12) consistent with multiple comparisons over 32 trials.

Rung 1 is the program's **honest control** (spec §3.2, rung B): a regime-weighted
ensemble of the same 16 signals. Its purpose is *not* to be the hypothesis — it is
the baseline that rung 2 (the distributional path model) must beat on identical
folds. If rung 2 cannot beat a regime ensemble, then any gain is ensembling +
regime, not path-modeling. Rung 1 must (a) beat rung 0 and (b) clear the DSR gate;
the likely-and-still-useful outcome is "ensembling helps but is not significant,"
which is exactly what makes a later rung-2 edge attributable.

## 1. Objective & scope

A regime-weighted ensemble that, per 4h bar, blends the firing signals'
regime-conditional path distributions into one LONG/SHORT/WAIT decision, scored
through the shared dual-frame harness over the same purged/embargoed folds as
rung 0, with the lockbox tail sealed.

**In scope:** the regime classifier, the per-(signal, regime) fit + weighting, the
market-frame weighted blend, an honest DSR calibration, an `ensemble` CLI
subcommand reporting rung 1 head-to-head against the rung-0 floor. **Out of scope:**
any learned model, grid search over the ensemble scheme, opening the lockbox,
adding features. Rung 1 is one frozen configuration.

## 2. Architecture

One new pure-consumer module + one CLI subcommand. No frozen interface
(`FEATURE_NAMES`, `Sample`, `Distribution`, `decide`, `evaluate_strategy`,
`walk_forward_folds`, `fit_distribution`, `_mirror`) is modified.

```
build_btc_dataset()  →  samples + folds                 (rung-0 data.py, reused)
generate_entries(family, params, bundle) → fire-map per signal   (reused, 16 signals)
                   ▼
  pathsig/ensemble.py
    assign_regimes(samples) → regime[pos]               (4-bucket, point-in-time)
    per fold:
      per (signal, regime): fit_distribution(train bars in regime) → D[s][r]   (rung-0 fn)
                            w[s][r] = max(0.0, edge of D[s][r])
      per TEST bar p (regime r):
        for each firing signal s: M = market-frame(D[s][r], side); weight w[s][r]
        ensemble = weight-normalized average of the M's  (WAIT if no weight)
        decide(ensemble) → Decision
    evaluate_strategy(decisions, LONG-frame labels, atr_fracs, fundings, ...) → dual frame
                   ▼
  tools/path_signal.py  `ensemble` subcommand → JSON {config, rung1, rung0_floor, verdict}
```

**Files:** create `src/moonface/research/pathsig/ensemble.py`; modify
`tools/path_signal.py`; test `tests/test_pathsig_ensemble.py`.

## 3. Regime classifier

`assign_regimes(samples, window=180) -> list[int]`: a **2×2 = 4-bucket** scheme
`{trend, range} × {low-vol, high-vol}`, computed per bar from the frozen feature
vector via a **trailing percentile rank** over the prior `window` samples,
point-in-time (only samples strictly before the current one enter the rank). Ranks
are self-normalizing, so **no thresholds are fit** (zero added trial-count):

- **vol axis:** trailing rank of `rvol_24` ≥ 0.5 → high-vol (1), else low-vol (0).
- **trend axis:** trailing rank of `abs(ma100_dist)` ≥ 0.5 → trend (1), else range (0).
- regime id = `trend_bit * 2 + vol_bit` ∈ {0,1,2,3}.
- bars before `window` past samples accumulate get a defined default (regime 0) but
  are rarely traded (signals/labels also warm up); the rank uses whatever prior
  samples exist (`< window` early on).

Direction (up/down) is deliberately **not** a regime axis — it is carried by each
signal's fired side, keeping all 4 cells populated. Feature indices are resolved by
`FEATURE_NAMES.index(...)`, never hard-coded.

## 4. Per-(signal, regime) fit and weighting

For each fold, each of the 16 `SIGNALS`, each of the 4 regimes:

- positions = train-fold sample positions where the signal fired **and**
  `regime[pos]` equals this regime.
- `D[s][r] = fit_distribution(samples, fire_s, positions, MIN_FIT_EVENTS)`
  (rung-0 signal-frame fit; `None`/dropped when below `MIN_FIT_EVENTS`).
- `w[s][r] = max(0.0, edge)` where `edge = D[s][r].exp_ret_r / abs(D[s][r].exp_mae_r)`
  (0.0 when `D` is `None`, `exp_mae_r == 0`, or edge ≤ 0). This is the signal's
  measured train drift-per-unit-MAE in that regime, clamped non-negative.

`fire_s = {candle_index: side}` from `generate_entries(family, params, bundle)`;
positioning families load their required metrics field on the bundle exactly as in
rung 0 (`_METRICS_FIELD`). A signal whose bundle lacks its series is simply absent
from the ensemble (no cells), not an error.

## 5. Test-bar combination (market-frame weighted blend)

For a test sample at position `p`, regime `r`:

1. Collect every signal `s` firing at `p` (i.e. `samples[p].index in fire_s`), with
   its side.
2. Convert each cell to the **market (LONG) frame**:
   `M = D[s][r]` if `side == "LONG"`, else `_mirror(D[s][r], "SHORT")`. Skip signals
   with `w[s][r] == 0` or `D[s][r] is None`.
3. If no signal contributes positive weight → emit `Decision("WAIT", 0.0)`.
4. Else the ensemble distribution is the **weight-normalized average** of the
   contributing `M`'s fields (`p_up`, `exp_ret_r`, `exp_mae_r`, `exp_mfe_r`), then
   `decide(ensemble, EDGE_THRESHOLD, KELLY_SCALE, MAX_FRACTION)`.
5. Realized R uses the **original LONG-frame label** `samples[p].label`
   (`evaluate_strategy`/`realized_r` apply direction). `atr_fracs` from
   `samples[p].x[FEATURE_NAMES.index("atr_frac")]`, `fundings` 0.0 (gross-of-funding
   path R, identical to rung 0).

Disagreeing signals net out in the average; a confidently one-sided regime produces
a decisive blend. The whole layer reuses rung-0 `fit_distribution`/`_mirror`/`decide`/
`evaluate_strategy` unchanged.

## 6. Evaluation, DSR calibration, beat-rung-0 verdict

- **Identical folds.** Same `walk_forward_folds(n_folds, embargo=h,
  lockbox_fraction=0.2)` over the same Sample grid as rung 0; lockbox sealed (rung 1
  does not open it).
- **DSR calibration (fixes the rung-0 `trial_srs=[]` gap).** Rung 1 feeds a real
  `trial_srs` = the per-trade Sharpes of the trials it considered, read directly from
  the rung-0 artifact: the `risk_adjusted.sharpe` of every `status=="ok"` baseline row
  **for the same horizon** (already computed on the identical Sample grid), with
  `n_trials = len(trial_srs)`. So `deflated_sharpe` deflates against an honest null
  rather than the empty-list default. (When the `--rung0` artifact is absent,
  `trial_srs` falls back to empty and the run logs that DSR is uncalibrated.) Rung 1
  itself is one frozen scheme (no grid), so it adds a single configuration.
- **Two-part verdict** (spec §3.2): the output reports rung 1 vs the rung-0 floor on
  both frames — (a) **beats rung 0**: ensemble `fixed_cap.total_r` and
  `risk_adjusted.{mar,sharpe}` vs the best rung-0 row; (b) **clears the gate**:
  `risk_adjusted.dsr ≥ 0.95`. A `verdict` block records `beats_rung0` (bool),
  `clears_gate` (bool), and a one-line interpretation. Given the rung-0 floor is
  ~nil, "beat rung 0" is a low bar; the gate is the real test.

## 7. CLI & output

`tools/path_signal.py` gains an `ensemble` subcommand:

```
python tools/path_signal.py ensemble \
    --out experiments/path_signal/rung1_ensemble.json \
    [--rung0 experiments/path_signal/rung0_baseline.json] \
    [--cache-dir .backtest_cache] [--n-folds 5] [--horizons 6 12]
```

Writes JSON: `config` (regime window, policy constants, folds, horizons, lockbox,
n_trials), `rung1` (per-horizon dual-frame result + regime cell coverage),
`rung0_floor` (best row per frame, read from the rung-0 artifact when supplied), and
`verdict`. Prints a compact rung1-vs-floor table to stdout. Offline-testable via an
injected `readers` dict (same pattern as rung-0 `run_baseline_to_doc`).

## 8. Testing strategy (TDD, flat per repo convention)

- `tests/test_pathsig_ensemble.py`:
  - `assign_regimes`: returns ids in {0,1,2,3}; is point-in-time (a late
    high-vol spike does not change an earlier bar's regime); high `rvol_24` /
    `abs(ma100_dist)` bars land in the expected buckets on a hand-built series.
  - weighting: `w` is 0 for a below-`MIN_FIT_EVENTS` or non-positive-edge cell, and
    equals `exp_ret_r/|exp_mae_r|` (clamped) for a positive cell.
  - market-frame blend: with two hand-built cells (one LONG-fire, one SHORT-fire)
    and known weights, the ensemble fields equal the manual weighted average; a bar
    with no firing signal → `WAIT`; opposing equal-weight signals net toward `WAIT`.
  - leak guard: shifting a test-fold label does not change any fitted cell.
  - end-to-end (synthetic readers): `run_ensemble_to_doc` returns the documented
    schema; `verdict.beats_rung0`/`clears_gate` are booleans; DSR ∈ [0,1].
  - CLI: `ensemble --out` on injected readers writes valid JSON with the schema.
- Full suite + `ruff check` over the new module and the CLI stay green.

## 9. Out of scope

- Rung 2 (distributional path model) and rung 3 (sequence model) — follow-on plans.
- Opening the lockbox tail — a rung-2 step.
- Grid search / tuning of the regime scheme or weighting — one frozen configuration.
- New features or data sources.

## 10. File structure

- Create: `src/moonface/research/pathsig/ensemble.py` — `assign_regimes`,
  `fit_regime_cells`, `ensemble_distribution`, `replay_ensemble`,
  `run_ensemble_to_doc`, regime constants.
- Modify: `tools/path_signal.py` — add the `ensemble` subcommand.
- Create: `tests/test_pathsig_ensemble.py`.
- Generated (force-add, gitignore convention):
  `experiments/path_signal/rung1_ensemble.json`.
