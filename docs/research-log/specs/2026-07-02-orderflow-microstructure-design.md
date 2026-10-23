# orderflow_microstructure v1 — Design Spec

Frozen **before any out-of-sample evaluation** of this program. A changed
design requires a new experiment directory. Lineage: the MoonFace 4h OHLCV
directional / funding / positioning program line has closed negative at the
4h–daily horizon (e.g. `funding_fade_voltarget`, closed negative 2026-07-02);
the single new lever here is the **intraday horizon** (15m bars, 5m-native
order-flow microstructure) paired with a **reversal-favoring exit** and
**intraday-tuned gates**. The thesis: the directional edge that is arbitraged
away at 4h may survive in short-horizon order-flow dislocations.

Pre-registration artifact (frozen gates, same content as §4–§6 below):
`experiments/orderflow_microstructure/PREREGISTRATION.md`.

---

## 1. Hypothesis

On **BTC/USDT:USDT** perp, **15m bars** with **5m-native order-flow
microstructure overlaid** (Binance Vision metrics archive), short-horizon
order-flow dislocation entries earn positive out-of-sample risk-adjusted
return **and** strictly beat a classic trend-breakout (`donchian_break`)
control on MAR and Sharpe — i.e. the edge that vanishes at 4h survives at
intraday. The reversals (`liquidity_sweep_reclaim`, `oi_flush_reversal`) are
the priority; `taker_flow_momentum` is a forced-flow **contrast** arm that
tests whether the edge is reversal-specific.

All three families and the control **already exist in the repo** and consume
the existing free-data plumbing. v1 adds **no new entry-family code** and **no
new data fetcher**; the new work is a bespoke domain runner that drives them
through intraday-tuned gates + a control-dominance check.

## 2. Construction (exact, pre-registered)

Asset / timeframe / data (identical across all specs unless noted):

```
exchange     = "binance"
symbol       = "BTC/USDT:USDT"          # Binance USDⓈ-M perp
timeframe    = "15m"                     # TIMEFRAME_MS["15m"] = 900_000 (supported)
metrics      = Binance Vision 5m archive via fetch_metrics_history (since 2020-09-01)
               aligned to 15m bars by align_metric (as-of join, no lookahead)
exit         = fixed_bracket{k_stop:2.0, m_tp:1.0, atr_period:14}
               # reversal-favoring: risk 2R to make 1R (gross break-even WR ≈ 66.7%).
               # _BRACKET_MAX_BARS=96 safety cap is dormant — ATR stop/TP resolve fast.
cost         = COST_FRACTION = 0.001 round-trip (≈ 9bps taker fee + slippage; locked)
               a 2× cost-stress column (0.002) is REPORTED but NON-GATING
```

Treatment families and their param grids (each cell = one HypothesisSpec):

- **`oi_flush_reversal`** — `metrics_field: "sum_open_interest"`. OI change over
  `lookback` bars, z-scored over `window`; `z ≤ −z_thr` flags forced
  deleveraging → fade the concurrent price move (liquidation-sweep reversal).
  - `{window:48,  lookback:6, z_thr:2.0}`
  - `{window:48,  lookback:6, z_thr:2.5}`
  - `{window:96,  lookback:6, z_thr:2.0}`
  - `{window:96,  lookback:6, z_thr:2.5}`

- **`taker_flow_momentum`** *(contrast)* — `metrics_field:
  "sum_taker_long_short_vol_ratio"`. Taker buy/sell-volume imbalance z-scored
  over `window`; `z ≥ z_thr → LONG`, `z ≤ −z_thr → SHORT` (follow aggression).
  - `{window:48, z_thr:2.0}`
  - `{window:48, z_thr:2.5}`
  - `{window:96, z_thr:2.0}`
  - `{window:96, z_thr:2.5}`

- **`liquidity_sweep_reclaim`** — pure price, no metrics. Bar wicks beyond the
  prior `swing_n` extreme but closes back inside → fade the sweep.
  - `{swing_n:48}`
  - `{swing_n:96}`

**Treatment grid = 4 + 4 + 2 = 10 specs. `n_trials = 10`** for the DSR
multiple-comparison correction.

Control (same asset / timeframe / exit; no metrics):

- **`donchian_break`** (classic trend breakout — the explicit contrast):
  - `{n:48,  long_only:False}`
  - `{n:96,  long_only:False}`

Control specs are evaluated for the dominance gate but are **not** promotion
trials and are excluded from `n_trials`.

## 3. Treatment vs control (the dominance gate)

Each treatment spec is paired against the `donchian_break` control **with the
matching lookback horizon** — `window`/`swing_n` = 48 ↔ control `n:48`; = 96 ↔
control `n:96` — holding the 15m timeframe, the `fixed_bracket` exit, the cost,
and the screen/holdout/lockbox splits identical. Only the **entry signal**
differs. A treatment spec is eligible for promotion only if it **strictly
dominates its paired control on both MAR and Sharpe** at holdout, at the
walk-forward aggregate, and at the lockbox tail. This operationalizes the
program thesis ("order-flow reversal instead of classic trend breakout") as a
falsifiable, paired comparison. (Both control variants are also excluded from
`n_trials`; they are reference baselines, not promotion seekers.)

## 4. Evaluation (hybrid ladder + walk-forward + control dominance)

Reuses `research/ladder.py` stage functions and the `voltarget_runner` bespoke
pattern. Intraday thresholds are applied via the **keyword overrides** the
stage functions already accept (`min_trades`, `min_mar`) — the frozen module
constants (`SCREEN_MIN_TRADES=30`, `LOCKBOX_MIN_TRADES=10`, etc.) are **not
mutated**, so concluded domains' DSR calibration is untouched.

- **Stage 1 — screen (70%):** `screen_trades ≥ 100` (override; raised from 30
  for intraday statistical power) **and** `screen_expectancy_R > 0`.
- **Stage 2 — holdout (30%):** `holdout_mar > 0` **and**
  `holdout_drawdown ≥ −0.30`.
- **Stage 3 — DSR:** `deflated_sharpe ≥ 0.95` with `grid_size = n_trials = 10`
  (the multiple-comparison backstop; screened-out specs still deflate).
- **Stage 3.5 — walk-forward:** rolling, **6-month train / 2-month test /
  2-month step** at 15m (~30 non-overlapping folds over the 2020-09→2026-07
  window). Requires `≥ 1 fold`, treatment aggregate MAR > 0, **and** dominance
  over the control on MAR & Sharpe.
- **Stage 4 — one-touch lockbox (final 20%, fence opened once):**
  `tail_mar ≥ 1.0`, `tail_trades ≥ 20` (override; raised from 10),
  `tail_drawdown ≥ −0.30`. The lockbox is opened only after a spec has
  survived stages 1 → 2 → 3.5 → DSR.
- **Dominance** (cross-cutting): treatment > control on MAR **and** Sharpe at
  holdout, WF aggregate, and lockbox tail.

## 5. Decision

- → **PAPER-LIVE WATCHING** iff **at least one treatment spec** clears stages
  1, 2, 3.5, DSR, **and** 4, **and** strictly dominates its `donchian_break`
  control at holdout, WF aggregate, and lockbox tail. The promoting family
  alone goes to watch; the other families are closed.
- → **CLOSED NEGATIVE** otherwise.

**Kill rule (pre-committed, no rescue):** on a closed-negative verdict there
is **no v2, no added family, no gate relaxation, no exit-ratio tuning**. The
intraday-horizon + reversal-exit lever is terminal for these families on a
closed-negative verdict. `n_trials = 10`.

## 6. Data, history window, and coverage

- 15m OHLCV: `fetch_history` (ccxt `binanceusdm`), cache-first. 15m is in
  `TIMEFRAME_MS`; no OHLCV plumbing change.
- Order-flow series: `fetch_metrics_history` → Binance Vision daily-zip
  archive, free, unauthenticated, **5-minute snapshots since 2020-09-01**.
  Fields used: `sum_open_interest`, `sum_taker_long_short_vol_ratio`. (The
  archive also exposes account & top-trader L/S ratios; not used in v1.)
- Window: **`ORDERFLOW_START_MS = 1_598_918_400_000` (2020-09-01 UTC) → run
  date** (~5.8 yr), bounded by metrics availability. `LOCKBOX_FRACTION = 0.2`
  → fence at the 80% point (~2025-05).
- Coverage gate: `load_bundle._check_coverage` requires ≥ 80% non-None on the
  aligned feature; the runner refuses to run on a gappy series.
- **Book-depth is excluded from v1** (`bookdepth_data` only covers 2023-01→)
  to maximize history; a book-depth liquidity-grab family is noted as a v2
  refinement. **Liquidation streams are not used** — free historical
  liquidation data is too sparse at usable granularity; the OI-flush + wick
  proxy in `oi_flush_reversal` / `liquidity_sweep_reclaim` is the
  reconstructable liquidation-sweep signal.

## 7. Runner architecture (reuses the bespoke domain-runner pattern)

Mirrors `src/moonface/research/voltarget_runner.py`:

- `src/moonface/research/orderflow_runner.py` — `register(store, now_ms)`
  (freeze window + fence + insert the 10 treatment + 2 control specs) and
  `run_domain(store, loader, out_root) -> "closed_positive" | "closed_negative"`
  (drives stages 1→2→3.5→DSR→4 with intraday overrides + control dominance;
  writes `experiments/orderflow_microstructure/<ts>/verdict.md`).
- `src/moonface/research/orderflow_wf.py` — rolling walk-forward
  (`walk_forward_paired`-style with 6mo/2mo/2mo at 15m) + `stage35` dominance
  check; mirrors `voltarget_wf.py`.
- `tools/research.py` — new `orderflow` subcommand (register + run), mirroring
  the `voltarget` subcommand.
- Config: `{"runner": "orderflow", ...}` so the generic `runner.run` skips this
  domain (the bespoke guard added for voltarget).
- Reuses unchanged: `Store` (registration + one-touch lockbox), `FencedBundle`,
  `ladder.evaluate_research` / `evaluate_lockbox` / `stage*_passed` /
  `stage3_dsr`, `single_trade_r`, `fixed_bracket`, `load_bundle`,
  `fetch_metrics_history`, `align_metric`.

## 8. Run

```
python tools/research.py orderflow
```
