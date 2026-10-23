# Drawdown-Aware Drift Screen — Design

- date: 2026-06-16
- status: design (approved, pre-implementation)
- branch context: research methodology; builds on `experiments/oibuild_study/` and the edge/exit probe history

## Motivation

The research program repeatedly found **directional drift** in several signal families
(breakouts, `funding_fade`, positioning) but never converted it into a tradeable,
drawdown-acceptable return. Every survivor died at the same place: either the drift's
own path blew through a sane stop, or bracketing it to control drawdown destroyed the
out-of-sample edge. High DSR readings (e.g. OI-build ~0.9 on ETH/SOL) were traced to
**exit-grid selection** — a multiple-comparisons artifact — not a real harvestable edge.

The user's proposed direction is the program's hard-won discipline stated forward:
**establish directional drift first (exit-free), optimize entry/exit only after.** This
is correct, but with one refinement the program learned the hard way: drift that is
merely *directional on average* is not enough — it must be **drawdown-acceptable**. The
existing mechanism test (`oibuild_study.py`) is **path-blind**: it scores only mean
directional return at horizon `h`. This design adds the missing path dimension.

## Goal

Two phases:

- **Phase A** — Quantify, from data already on disk, the gap between "drift exists" and
  "drift survives its own drawdown," and derive the empirical floor for Phase B.
- **Phase B** — Build a reusable, exit-free, **path-aware** mechanism screen
  (`drift_screen.py`), generalizing `oibuild_study.py`, and re-score the existing signal
  registry under it on fresh assets. Settle whether the "drawdown wall" is a real
  structural fact or a metric artifact of having only ever scored mean return.

## Non-Goals

- No exit/stop/TP grid search. The screen is deliberately exit-free — a single horizon
  `h`, no tunable bracket. This is the discipline that prevents manufacturing false
  positives.
- No new signal family in this work (that is a possible follow-up). Phase B re-scores the
  **existing** registry only.
- No promotion/lockbox interaction. This produces evidence and a verdict, not a deployed
  strategy.

## Phase A — Characterize the Gap (analysis, no new production code)

Mine three result sets already on disk and produce one descriptive report.

Sources:
- Edge leaderboard — `experiments/edge/20260609T171708Z/leaderboard.{md,json}`.
  Columns of interest: `hzn OOS exp` (exit-free horizon drift) vs `brkt net R`
  (exit-applied). Shows drift present, exit destroying it (e.g.
  `atr_channel_break|pivot_bias`: +1.27 horizon OOS exp, −9.6 bracket net R).
- Positioning exit probe — `experiments/positioning_exits/20260610T065146Z/positioning_exit_probe.{md,json}`.
  The smoking gun: `funding_fade + horizon_hold` = OOS **+111R / +1.63 exp** but
  research **maxDD −114R**; bracketing cuts maxDD to ~−32R but collapses OOS R.
- OI-build verdict — `experiments/oibuild_study/verdict.json`. The
  `mechanism_does_not_exist` null baseline (pooled −0.0064/event, sign test 8/16).

Output (`experiments/drift_screen/phaseA_gap.md`, descriptive only):
1. Per-family table: drift magnitude (horizon OOS exp / mean directional ret) vs max
   adverse excursion (maxDD R) vs **cost-of-DD-control** — how much OOS R dies when a
   fixed bracket is applied to bring maxDD within the program's standing −15R budget.
2. The empirical distribution of the **ret/|mae|-equivalent ratio** that the known dead
   families exhibited.
3. The **calibrated MAE-ratio floor** for Phase B: the `mean(ret_r)/mean(|mae_r|)` value,
   set so that the families already known to be dead fail it, expressed as a single
   pre-registered number. This is the one output of Phase A that Phase B consumes.

Phase A writes no code under `src/`. It may use a throwaway analysis script under
`experiments/drift_screen/` to parse the JSON, but the deliverable is the report + the
chosen floor.

## Phase B — Drawdown-Aware Mechanism Screen (new module)

New pure module: `src/moonface/research/drift_screen.py`. Generalizes the structure of
`oibuild_study.py` and reuses its statistics where identical.

### Reused verbatim from `oibuild_study.py`
- `nonoverlap(events, h)` — serial-dependence guard.
- `binom_p_geq`, `stouffer`, `asset_stats` — pooled statistics.
- Per-asset = one unit of evidence; raw events never pooled across assets.
- Tripartite verdict shape: `mechanism_exists` / `mechanism_does_not_exist` /
  `inconclusive`.

### Discretion principle (formula/parameter choices)
Where this design leaves a formula or parameter open, the choice is exercised toward
**correctness and conservatism — never toward pass-rate.** A definition is chosen because
it most faithfully measures the quantity (adverse excursion, drift) or because it makes
the test *stricter*, not because it makes more families pass. Selecting any knob on the
outcome is the exact mechanism (`oibuild` exit-grid DSR 0.9) this screen exists to avoid.
The one explicitly outcome-coupled value — the floor — is neutralized by pre-registering
it against *known-dead* families before any real run (see Open Risks).

### New: per-event path-aware outcome
Outcomes are measured in **R units** (excursion / ATR-at-entry), matching the program's
universal R denominator (`_risk` / `_r_unit` in `edge/exits.py`) and the standing −15R
drawdown budget — so the screen's drawdown is directly comparable to every prior probe.

For each event at bar `i` with side `LONG`/`SHORT`, over a fixed horizon `h`, let
`unit = _r_unit(candles, i, atr_period)` (1×ATR at the entry bar, lookahead-free; the
event is discarded when `unit` is None — last bar / ATR <= 0):

```
# directional forward move in R, sign-adjusted by side:
ret_r = side_sign * (close[i+h] - close[i]) / unit
# worst intra-horizon excursion AGAINST the position, in R, using the same
# low/high convention as _fill() (LONG adverse = bar.low, SHORT adverse = bar.high):
LONG :  mae_r = min over 1<=k<=h of (low[i+k]  - close[i]) / unit     # <= 0
SHORT:  mae_r = min over 1<=k<=h of (close[i] - high[i+k]) / unit     # <= 0
```

`mae_r` is always <= 0 (the adverse drawdown, in R, the position lived through before
horizon — same sign convention as `summarize_r.max_drawdown_r`). Events without `h`
future bars are discarded (matches existing guard). MAE is the plain adverse extreme over
the window; the pessimistic stop-first `_fill` convention is an *exit* concern and does
not apply to a path measurement.

This requires **OHLC candles** (low/high + ATR), not the daily close-only `DailyRow` that
`oibuild_study` universe-selection uses.

### Two-part pooled gate (frozen before the real run)
A family passes only if **both** hold on the fresh-asset pool:
1. **Drift exists** — sign test on per-asset mean `ret_r`: `p_sign <= 0.05` AND
   Stouffer `Z >= 1.645` (identical criteria to oibuild).
2. **Drift survives its path** — pooled `mean(ret_r) / mean(|mae_r|)` ratio `>= FLOOR`,
   where `FLOOR` is the Phase A calibrated value (a unitless R/R ratio).

Verdict:
- both pass → `mechanism_exists`
- drift fails OR pooled mean `ret_r` <= 0 → `mechanism_does_not_exist`
- drift passes but ratio below floor → `inconclusive` (drift real but path-unacceptable —
  the "wall" stated precisely)

### Inputs
- **Signals**: existing registry, `src/moonface/backtest/edge/signals.py` (donchian_break,
  atr_channel_break, ma_cross, roc_sign, price_vs_ma, reversion_in_range, etc.) plus
  funding/positioning signals as available. Re-scored under the path-aware gate.
- **Universe**: the 16 fresh oibuild assets, 4h OHLC from `.backtest_cache/*USDT_4h.csv`
  (already cached; low/high present). The discovery set (BTC/ETH/SOL) is excluded from
  evidence exactly as oibuild excludes it.
- **Horizon**: single fixed `h` (default 24 bars = oibuild's primary endpoint), no grid.

### Output
- `experiments/drift_screen/PREREGISTRATION.md` — frozen `h`, `FLOOR`, universe, exclude
  set, gate rule. Committed **before** the real run.
- `experiments/drift_screen/leaderboard.{md,json}` — per-signal: pooled ret, pooled |mae|,
  ratio, sign-test p, Stouffer Z, verdict. Ranked.
- A `verdict.json` per signal mirroring oibuild's schema.

Expected result: few or no survivors, but now **proven** under a path-aware metric —
either confirming the drawdown wall is real, or surfacing a family whose drift/MAE ratio
clears the floor (a genuine lead).

## Testing (TDD)

- Synthetic series with **known drift + known drawdown** → asserts `ret`, `mae`, and ratio
  hit hand-computed values, and that the verdict rule fires correctly across all three
  branches.
- A synthetic "pure drift, no adverse excursion" series → `mechanism_exists`.
- A synthetic "drift present but deep mid-horizon dip" series → `inconclusive` (path fails).
- A synthetic "no drift" series → `mechanism_does_not_exist`.
- Parity test: reused stats functions (`binom_p_geq`, `stouffer`, `asset_stats`) produce
  identical results to `oibuild_study` on shared inputs.
- Pre-registration file committed before the real-data run (program convention).

## Open Risks

- **Phase A↔B coupling**: the floor is data-derived, so Phase A must be honest — the floor
  is set to make *known-dead* families fail, not reverse-engineered to pass a favorite.
  Mitigation: floor is a single pre-registered number, committed before any Phase B real
  run, and the report records why that value.
- **MAE on 4h candles understates intrabar drawdown** (true worst tick is below the 4h
  low). This biases the screen *conservative* (real MAE is worse), which is acceptable —
  a family that passes on 4h-low MAE is, if anything, understated in difficulty. Noted,
  not corrected.
- **Cached-data drift**: `.backtest_cache` 4h CSVs are dirty in git status. The run records
  the data hash/asof so the verdict is reproducible.
