# Drift screen — pre-registration (frozen before any real run)

This document freezes the design of the drawdown-aware drift screen **before**
the screen is run on real cached 4h candles. The design, the floor, the
universe, and the signals below are immutable for this run. The code (Tasks
1-10) already exists; this task only commits the frozen design and the verdicts
it produces.

## Frozen design

- **Timeframe:** 4h bars.
- **Frozen horizon:** `h = 24` (4h bars). A single fixed horizon is scored.
- **ATR period:** `atr_period = 14`.
- **Calibrated floor:** `0.1319` (frozen from Phase A; see below).

### Calibrated floor (frozen)

The floor is the largest `drift_r / |dd_r|` ratio observed among known-dead
drifting families in Phase A, calibrated against the existing edge and
positioning-exit result files. Phase A wrote:

> `- **calibrated floor (ret_r/|mae_r|): 0.1319**`

This value is frozen here before any real run. The gate `ratio >= floor`
therefore rejects every family already known to be dead.

## Universe (16 fresh-asset confirmation set)

The screen runs over the 16 fresh confirmation assets from the OI-build study
(these are the assets the OI-build mechanism verdict was rendered on, none of
which were in the discovery set):

1. `1000PEPEUSDT`
2. `PEOPLEUSDT`
3. `DOGEUSDT`
4. `BNBUSDT`
5. `1000SHIBUSDT`
6. `1000FLOKIUSDT`
7. `XRPUSDT`
8. `LINKUSDT`
9. `HIGHUSDT`
10. `NEARUSDT`
11. `JASMYUSDT`
12. `TRBUSDT`
13. `FILUSDT`
14. `ARBUSDT`
15. `AVAXUSDT`
16. `ETCUSDT`

### Excluded discovery set

The discovery assets used to find these signals are excluded from this
confirmation run:

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`

## Registered signals (7)

The 7 existing-registry signals re-scored on the fresh universe:

| # | signal | params |
|---|--------|--------|
| 1 | `donchian_break` | `{n: 100}` |
| 2 | `donchian_break` | `{n: 55}` |
| 3 | `atr_channel_break` | `{k: 1.5, atr_period: 14}` |
| 4 | `atr_channel_break` | `{k: 2.0, atr_period: 14}` |
| 5 | `ma_cross` | `{fast: 50, slow: 200}` |
| 6 | `roc_sign` | `{period: 24}` |
| 7 | `price_vs_ma` | `{period: 100}` |

## Minimum-evidence thresholds

- `min_events = 10` (per asset; an asset with fewer events for a signal is
  dropped from that signal's aggregate).
- `min_assets = 8` (a signal with fewer than 8 qualifying assets is
  `inconclusive` — insufficient assets).

## MAE-in-R convention

Per-event maximum adverse excursion is measured **in R units**, where R is the
ATR at entry. The excursion is `bar.low / ATR_at_entry` for LONG entries and
`bar.high / ATR_at_entry` for SHORT entries, scanned over the `h` bars after
entry, and the **maximum** adverse excursion across those bars is recorded.

Exit-free: no stops, take-profits, or grids of any kind are fit. A single
fixed horizon is scored.

## Two-part gate + tripartite verdict

For each signal the screen computes, per qualifying asset, the mean
`ret_r` (per-event forward return in R units over the horizon) and the mean
`abs(mae_r)` (per-event maximum adverse excursion in R units). The two-part
gate is:

1. **Drift exists.** A sign test on per-asset `mean_ret_r` yields
   `p_sign <= 0.05` **AND** a Stouffer Z-test on per-asset `mean_ret_r`
   yields `Z >= 1.645`.
2. **Drift survives the path.** The pooled `mean_ret_r` divided by the pooled
   `mean_|mae|_r` (i.e. `pooled_ret_r / pooled_abs_mae_r`) is `>= floor`
   (`0.1319`).

The verdict is tripartite:

- **`mechanism_exists`** — both parts pass (drift exists AND drift survives).
- **`mechanism_does_not_exist`** — drift fails (sign test or Stouffer fails),
  **or** `pooled_ret_r <= 0`.
- **`inconclusive`** — drift passes the existence test but `ratio < floor`,
  OR fewer than `min_assets` (8) assets qualify.

## Frozen statement

No exits, stops, take-profits, or grids of any kind are fit; a single fixed horizon is scored. The floor was calibrated against known-dead families in Phase A and is frozen here before any real run.
