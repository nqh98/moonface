# Multi-family exit-free drift screen — design

- **Date:** 2026-06-16
- **Status:** Approved, pre-implementation
- **Extends:** `src/moonface/research/drift_screen.py` (single-horizon, candles-only,
  price-structure screen — commit `07d3e6e`, verdict: all 7 price signals
  `mechanism_does_not_exist`).

## Goal

Discover repeatable directional drift in crypto futures markets across feature
families that the existing drift screen never covered, using the same
mechanism-first, exit-free, path-aware, breadth-gated discipline. This is a
**drift-discovery** task, not strategy optimization: no exits, stops,
take-profits, trailing stops, position sizing, or grids are fit. A family is
promoted to strategy design only after it demonstrates robust directional drift
that survives cross-asset validation.

## Non-goals

- No exit/stop/TP/trailing/sizing optimization of any kind (forbidden until a
  family passes drift + breadth + drawdown-profile tests).
- No basis, lead-lag, liquidations, or cross-exchange families — they lack broad
  16-asset data for a valid breadth test (only BTC spot for basis; BTC+ETH for
  lead-lag; no liquidation or cross-exchange data cached). Out of scope.
- No tuning of any signal after seeing results. Definitions are frozen in
  `PREREGISTRATION.md` before the run.

## Scope: three families

| Family | Signals | Mechanism hypothesis | Direction |
|---|---|---|---|
| **Funding** | `funding_fade`, `funding_confirm`, `funding_flip` | Crowded carry pays to fade; persistent funding confirms trend | existing generators |
| **OI / positioning** | `oi_build_momentum`, `oi_flush_reversal`, `toptrader_follow`, `taker_flow_momentum` | New money follows the move; deleveraging flush overshoots; top-trader and aggressive-taker imbalance lead | existing generators |
| **Orderbook imbalance** | `ob_imbalance_follow` (**new**) | Resting ±1% depth imbalance is informed pressure → short-horizon continuation | follow |

All signals are pre-registered with one direction each, chosen from the
mechanism, not from the data.

## Data feasibility (fresh 16-asset 4h pool)

Verified present in `.backtest_cache/`:

- **Funding** — `unifunding_<SYM>.csv` across the pool.
- **OI / positioning** — `metrics_<SYM>.csv` (columns: `sum_open_interest`,
  `sum_open_interest_value`, `sum_toptrader_long_short_ratio`,
  `count_toptrader_long_short_ratio`, `count_long_short_ratio`,
  `sum_taker_long_short_vol_ratio`), 16 assets.
- **Orderbook imbalance** — `bookdepth_<SYM>.csv` (±1% band bid/ask notional,
  ~30s snapshots), 16 assets, loaded by `moonface.backtest.bookdepth_data`.

Universe = the 16 fresh confirmation assets already frozen in
`experiments/drift_screen/PREREGISTRATION.md` (1000PEPE, PEOPLE, DOGE, BNB,
1000SHIB, 1000FLOKI, XRP, LINK, HIGH, NEAR, JASMY, TRB, FIL, ARB, AVAX, ETC).
Discovery assets BTC/ETH/SOL are excluded.

## Architecture

### 1. Generalize `drift_screen` to bundle-aware generators

Today `drift_screen.Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]`
(candles only). The non-price families need a per-asset `DataBundle` (candles +
funding + metrics feature + bookdepth).

Change: the screen calls `entries.generate_entries(family, params, bundle)`
instead of a bare candles-only callable. The price path is preserved because a
price family's bundle carries only candles, and `generate_entries` already
routes price families to the candles-only generators. No price-screen behavior
changes.

`score_signal_on_asset` / `screen_signal` take `(family, params, bundle)` per
asset instead of `(generator, params, candles)`. `event_outcome` is unchanged —
it still scores `(i, side)` events against candles.

### 2. New orderbook imbalance generator

New module `src/moonface/backtest/edge/ob_imbalance_signals.py`:

- Per 4h bar, imbalance `= (bid_1pct − ask_1pct) / (bid_1pct + ask_1pct)`,
  computed as the **mean over the ~30s snapshots falling inside that bar**
  (bars with no snapshots → `None`, gap-tolerant like the metrics loader).
- `make_ob_imbalance_follow(feature)` returns a generator mirroring
  `positioning_signals._make_level_follow`: z-score the per-bar imbalance over a
  rolling `window`; `z ≥ z_thr → LONG`, `z ≤ −z_thr → SHORT`. Symmetric by
  construction (strong bid imbalance → LONG drift; strong ask imbalance → SHORT
  drift).
- Registered in `entries.py` (`ob_imbalance_follow`), reading
  `bundle.bookdepth` (new optional `DataBundle` field). Raises `ValueError` if
  the family is requested without bookdepth data, matching the existing
  funding/feature guards.
- Pre-registered params (frozen): `window ∈ {180}`, `z_thr ∈ {1.5, 2.0}` — the
  same narrow grid shape the positioning families use, kept small to bound the
  comparison count. **No tuning after results.**

### 3. Per-asset bundle loader

A loader that, for each of the 16 pool symbols, assembles a `DataBundle` with
4h candles + funding + the chosen metrics field + bookdepth-imbalance series,
applying the same coverage/freshness gating the existing per-family loaders use.
A symbol that fails coverage for a given family is dropped from that family's
aggregate (it falls below `min_events`/`min_assets`, not silently zero-filled).

## Statistics (per the research prompt)

Extend `event_outcome` and `asset_path_stats`:

- **ret_r** — forward return in R over the horizon (existing).
- **MAE in R** — worst adverse excursion, ≤ 0 (existing).
- **MFE in R** — best favorable excursion, ≥ 0 (**new**; mirror of MAE using
  `bar.high` for LONG, `bar.low` for SHORT).
- **Per-event sign rate** (**new**) — fraction of events with `ret_r > 0`,
  pooled and per-asset.
- **Stouffer Z**, **breadth (k-positive / m-assets)**, **pooled mean ret_r**,
  **pooled mean |MAE|** (existing).

## Multi-horizon

- **Descriptive curve** at `h ∈ {3, 6, 12, 18, 24}` 4h bars (= 12h, 24h, 48h,
  72h, 96h). 6h is sub-bar on 4h candles and is omitted. For every signal,
  report ret_r, sign rate, MAE, MFE, and Stouffer Z at each horizon. The curve
  is **evidence of shape/decay only — never additional PASS chances**.
- **Binding PASS/FAIL at exactly one frozen primary horizon per family:**
  - Orderbook imbalance → `h = 3` (12h; microstructure decays in hours).
  - Funding → `h = 6` (24h).
  - OI / positioning → `h = 6` (24h).
- One binding horizon per family = one comparison per signal, preserving the
  program's single-comparison discipline.

## Path floor recalibration

The existing floor `0.1319` was calibrated against known-dead families **at
h=24** (Phase A of the original drift screen). It is not valid at other
horizons.

- **Phase A (re-run per primary horizon):** recompute the floor as the largest
  `pooled_ret_r / pooled_|MAE|` ratio observed among the known-dead rows at that
  horizon, using the same source result files the original calibration used.
- `h = 6` may reproduce `0.1319`; `h = 3` gets its own freshly calibrated value.
- Both floors are **frozen in `PREREGISTRATION.md` before any real screen run.**

## Verdict & discipline

Reuse the existing tripartite gate (`drift_screen.drift_verdict`):

1. **Drift exists** — sign test `p ≤ 0.05` AND Stouffer `Z ≥ 1.645` on per-asset
   mean ret_r.
2. **Drift survives the path** — `pooled_ret_r / pooled_|MAE| ≥ floor` (the
   horizon-matched frozen floor).

Verdict:
- `mechanism_exists` — both parts pass.
- `mechanism_does_not_exist` — drift fails, or `pooled_ret_r ≤ 0`.
- `inconclusive` — drift exists but ratio < floor, or fewer than `min_assets`
  (8) qualifying assets.

Thresholds reused: `min_events = 10` per asset, `min_assets = 8`.

## Pre-registration

A new `experiments/drift_screen_multifamily/PREREGISTRATION.md` freezes, before
any real run: the universe (16 fresh assets), the three families and their
signals/params/directions, the per-family primary horizons, the descriptive
horizon set, the recalibrated per-horizon floors, and the frozen statement that
no exits/stops/TPs/grids are fit. The orderbook signal definition is frozen
verbatim and not tuned after results.

## Output

Per family, per signal: mechanism hypothesis, assets tested, sample size,
forward-return curve (ret_r at each horizon), sign-rate curve, MAE/MFE curve,
breadth (k/m), Stouffer Z, the binding-horizon path ratio vs floor, and the
tripartite verdict. A leaderboard (`leaderboard.json` + `.md`) mirroring the
existing drift-screen artifacts.

## Promotion rule

Only a family that returns `mechanism_exists` (positive pooled return, positive
breadth, significant directional consistency, acceptable drawdown profile,
replicated across the fresh pool) is eligible to proceed to entry/exit/risk
design, backtesting, OOS validation, and DSR evaluation — a separate program
with its own discipline. The objective here is to discover a real, repeatable
directional effect, not a profitable backtest.

## Testing

- Unit: per-bar imbalance aggregation (snapshot→bar mean, gap → None);
  `ob_imbalance_follow` symmetry (mirrored series → mirrored sides); MFE sign
  and magnitude; per-event sign rate; floor recalibration on a synthetic
  known-dead row.
- Integration: `screen_signal` over a synthetic 2-asset bundle for one family of
  each kind (candles-only price path still works; bundle path produces a
  verdict).
- Regression: existing price-family screen output is unchanged after the
  generator generalization.
