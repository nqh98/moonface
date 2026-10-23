# Multi-family drift screen — pre-registration (frozen before any real run)

This document freezes the design of the exit-free, drawdown-aware drift screen
extended across the **funding, OI/positioning, and orderbook-imbalance**
feature families **before** the screen is run on real data. The design, the
per-family primary horizons, the per-horizon floors, the universe, and the nine
registered families below are immutable for this run. The code (Tasks 1-8)
already exists; this task only commits the frozen design and the verdicts it
produces.

## Frozen design

- **Timeframe:** 4h bars.
- **Per-family primary horizon** (4h bars; the one horizon used for PASS/FAIL):
  orderbook `h = 3`, funding and OI/positioning `h = 6`.
- **ATR period:** `atr_period = 14`.
- **Calibrated floors:** `0.1319` at both `h = 3` and `h = 6` (frozen from
  Phase A; see below).
- **Descriptive curve horizons:** `{3, 6, 12, 18, 24}` (non-binding term
  structure only; no PASS/FAIL).

### Calibrated floors (frozen)

The floor is the largest `drift_r / |dd_r|` ratio observed among known-dead
drifting families in Phase A, recalibrated against the same existing edge and
positioning-exit result files the price screen used. Because the dead-row
ratios are horizon-agnostic R magnitudes (`oos_expectancy_r / |research_max_dd_r|`
for positioning, `horizon_oos_expectancy_r / |bracket_net_r|` for edge), the
floor is identical at every primary horizon. Phase A wrote, at both horizons:

> `- **calibrated floor (ret_r/|mae_r|) at h=3: 0.1319**`
> `- **calibrated floor (ret_r/|mae_r|) at h=6: 0.1319**`

Calibrated from 39 known-dead rows (25 positioning-exit + 14 edge), largest
ratio `1.2666 / 9.6047 = 0.1319`. This matches the price screen's frozen floor
exactly. These values are frozen here before any real run, so the gate
`ratio >= floor` rejects every family already known to be dead.

## Universe (16 fresh-asset confirmation set)

The screen runs over the 16 fresh confirmation assets (the same set the
OI-build mechanism verdict was rendered on; none were in the discovery set):

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

The discovery assets are excluded from this confirmation run:

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`

## Registered families (9)

Each family is scored exit-free at its frozen primary horizon:

| # | family | params | primary h |
|---|--------|--------|-----------|
| 1 | `funding_fade` | `{window: 60, z_thr: 1.5}` | 6 |
| 2 | `funding_confirm` | `{persist: 6, lvl: 0.0003}` | 6 |
| 3 | `funding_flip` | `{debounce: 6}` | 6 |
| 4 | `oi_build_momentum` | `{window: 180, lookback: 6, z_thr: 1.5}` | 6 |
| 5 | `oi_flush_reversal` | `{window: 180, lookback: 6, z_thr: 1.5}` | 6 |
| 6 | `toptrader_follow` | `{window: 180, z_thr: 1.5}` | 6 |
| 7 | `taker_flow_momentum` | `{window: 180, z_thr: 1.5}` | 6 |
| 8 | `ob_imbalance_follow` | `{window: 180, z_thr: 1.5}` | 3 |
| 9 | `ob_imbalance_follow` | `{window: 180, z_thr: 2.0}` | 3 |

The `funding_confirm` params follow the canonical `CONFIRM_GRID` row from
`tools/funding_probe.py` (`persist`/`lvl`, not window/z-threshold).

### Metrics-field routing

Positioning families read a metrics series from `bundle.feature`; funding and
orderbook families ignore `feature`. Each distinct metrics field gets its own
pool:

- `oi_build_momentum`, `oi_flush_reversal` → `sum_open_interest`
- `toptrader_follow` → `sum_toptrader_long_short_ratio`
- `taker_flow_momentum` → `sum_taker_long_short_vol_ratio`
- funding / orderbook families → default pool (`sum_open_interest`, unused)

## Minimum-evidence thresholds

- `min_events = 10` (per asset; an asset with fewer non-overlapping tradeable
  events for a family is dropped from that family's aggregate).
- `min_assets = 8` (a family with fewer than 8 qualifying assets is
  `inconclusive` — insufficient breadth).

An asset whose bundle lacks the family's required series (funding/feature/
bookdepth) contributes no evidence and is skipped for that family only.

## MAE/MFE-in-R + sign-rate convention

Per-event outcome is `(ret_r, mae_r, mfe_r)` in R units, where R is the ATR at
entry, scanned over the `h` bars after entry:

- `ret_r` = side-weighted forward return to `close[i+h]`, in R.
- `mae_r` = **maximum adverse excursion** (worst move against the position),
  `<= 0`: `bar.low` for LONG, `bar.high` for SHORT.
- `mfe_r` = **maximum favorable excursion** (best move in favour), `>= 0`:
  `bar.high` for LONG, `bar.low` for SHORT.

Per-asset stats add `mean_mfe_r` and `sign_rate` (fraction of events with
`ret_r > 0`) alongside the existing `mean_ret_r`, `mean_abs_mae_r`, and the
`ret_r` t-stat (reusing oibuild's `asset_stats` so the magnitude test is
identical across studies).

Exit-free: no stops, take-profits, or grids of any kind are fit. A single
fixed primary horizon is scored per family.

## Two-part gate + tripartite verdict

For each family the screen computes, per qualifying asset, `mean_ret_r`,
`mean_abs_mae_r`, `mean_mfe_r`, `sign_rate`, and the `ret_r` t-stat. The
two-part gate (at the family's primary horizon, under its horizon-matched
floor) is:

1. **Drift exists.** A sign test on per-asset `mean_ret_r` yields
   `p_sign <= 0.05` **AND** a Stouffer Z-test on per-asset `mean_ret_r`
   yields `Z >= 1.645`.
2. **Drift survives the path.** The pooled `mean_ret_r` divided by the pooled
   `mean_abs_mae_r` (`pooled_ret_r / pooled_abs_mae_r`) is `>= floor`
   (`0.1319`).

The verdict is tripartite:

- **`mechanism_exists`** — both parts pass (drift exists AND drift survives).
- **`mechanism_does_not_exist`** — drift fails (sign test or Stouffer fails),
  **or** `pooled_ret_r <= 0`.
- **`inconclusive`** — drift passes the existence test but `ratio < floor`,
  OR fewer than `min_assets` (8) assets qualify.

## Descriptive multi-horizon curve (non-binding)

Each family also carries a descriptive term structure over `{3, 6, 12, 18, 24}`
bars (pooled `ret_r`, `sign_rate`, `|mae|`, `mfe`, Stouffer Z per horizon). This
is **evidence of drift shape/decay only** — no floor, no PASS/FAIL. The binding
verdict is the two-part gate at the family's frozen primary horizon above.

## Data availability (as run)

The screen loads the most recent **365 days** of 4h history (`--days 365`), not
the price screen's 3-year default. The window is data-loading scope, not a frozen
mechanism parameter (the registration froze the families, horizons, floors, and
universe — never a window). One year is 2190 4h bars, ample for the ≤180-bar
rolling windows, and was chosen for tractability: the fresh universe's funding
and bookdepth archives are not pre-cached, and a 3-year ccxt pull is
rate-limit-bound (~4 min/asset); a 1-year pull is ~6 s/asset. This window was
fixed before any family verdict was observed.

Cached 4h candles and the metrics fields are present for all 16 universe
assets. Per-bar mean bookdepth (±1% band imbalance) is cached for 13 of 16
(`ARBUSDT`, `AVAXUSDT`, `ETCUSDT` lacked it at freeze time; they are fetched
from the Binance Vision bookDepth archive for the 1-year window, so the
orderbook family screens on whichever assets clear `min_assets`). Funding is
fetched from the Binance futures archive for the fresh universe (historical and
deterministic; cached on first fetch). None of these availability facts change
which families are registered or the floor — a family with insufficient breadth
simply reads `inconclusive`.

## Frozen statement

No exits, stops, take-profits, or grids of any kind are fit; a single fixed
primary horizon is scored per family. The per-horizon floors were calibrated
against known-dead families in Phase A and are frozen here before any real run.
The orderbook-imbalance definition and family parameters are not tuned after
the results are observed.
