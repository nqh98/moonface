# universe_donchian v1 — Design Spec

Frozen **before any out-of-sample evaluation** of this program. A changed
design requires a new experiment directory. Lineage: the deployed Donchian
breakout trend-follower (`trend_sim.simulate_donchian`, `TrendParams(entry_n=40,
trail_n=20, atr_period=14, k_stop=2.0)`, 4h) has decayed on BTC — per
`experiments/deployable/DONCHIAN_RECENCY_2026-06-25.md`, BTC/USDT 4h was
−1.54R in 2025, −8.65R YTD 2026, −11.76R trailing-365d ("the deployed config
is not currently demonstrating its edge out of sample"). The single new lever
here is **the traded universe**: the engine's entries/exits are byte-frozen;
only *which symbols* it trades changes. The thesis: the trend-breakout edge
that BTC's increasingly efficient 2025–2026 structure has arbitraged away may
survive on less-efficient altcoin perps whose retail/narrative-driven volume
expansions produce stronger, slower trends — and a daily **abnormal
quote-volume expansion** screen is the pre-specified way to find them.

Pre-registration artifact (frozen gates, same content as §4–§6 below):
`experiments/universe_donchian/PREREGISTRATION.md`.

---

## 1. Hypothesis

On a **dynamic top-5 altcoin USDT-perp universe** (rebuilt weekly from a
survivorship-clean Binance USDⓈ-M enumeration, selected each period by
abnormal 24h quote-volume expansion with liquidity and listing-age floors),
the **frozen deployed Donchian breakout engine** (4h, `long_only=False`)
earns positive out-of-sample risk-adjusted return **and** strictly beats a
**static broad alt basket control** (same filters, equal-weight, no
expansion ranking) on MAR and Sharpe — i.e. the *volume-expansion selection*
specifically revives edge that decayed on BTC. BTC/USDT (the decayed engine)
is reported as a non-gating absolute-revival reference.

The engine already exists and is frozen. v1 adds **no new entry/exit code**
and **no new data fetcher**; the new work is (a) a point-in-time abnormal-
expansion universe screener and (b) a bar-by-bar mark-to-market portfolio
simulator that blends the per-symbol Donchian trades into one equity curve.

## 2. Construction (exact, pre-registered)

Engine, asset class, cost, window (identical across all specs unless noted):

```
exchange     = "binanceusdm"                      # Binance USDⓈ-M perps (fapi / Vision S3)
universe     = list_um_perp_symbols()             # survivorship-clean, INCLUDES delisted
engine       = trend_sim.simulate_donchian        # FROZEN — see TrendParams below
timeframe    = "4h"                                # the deployed engine's timeframe
params       = TrendParams(entry_n=40, trail_n=20, atr_period=14, k_stop=2.0,
                          long_only=False, fee_rate=0.00045, slippage=0.0005,
                          funding_enabled=True, exit_mode="trail")
               # long_only=False is the ONLY non-deployed knob: it enables the
               # short side. Entry/exit channel logic is byte-identical to the
               # deployed engine; `long_only` is a pre-existing TrendParams flag,
               # not a new entry/exit invention.
cost         = COST_FRACTION = 0.001 round-trip (≈ taker fee + slippage, locked;
               foundation/metrics.py:211). Applied per trade in the portfolio
               bar-sim. A 2× cost-stress (0.002) is REPORTED but NON-GATING.
funding      = held funding over each position (research/funding_cost.py); long
               pays +rate, short receives. Folded into the bar-sim mark-to-market.
window       = START = 2021-01-01 UTC → run date (≈5.5 yr). Alt universe is
               sufficiently populated from 2021; the 30-day volume baseline and
               90-day age floor thin the universe naturally early (point-in-time
               correct). LOCKBOX_FRACTION = 0.2 → fence ≈ 2025-05 (the tail
               deliberately overlaps the BTC-decay period 2025–2026).
sizing       = fixed total gross G = 1.0 per unit equity; per-slot fraction
               f_slot = G / (slot count): treatment f_slot = G/top_n (5 → 0.20,
               10 → 0.10), control f_slot = G/N_qualifiers. A slot contributes
               f_slot × side × bar_pct_return while its Donchian position is open,
               0 (cash) while flat. MAX_LEVERAGE = 5.0 respected (G = 1.0 ≤ cap).
               The 2× cost-stress column reuses the same sizing.
```

Universe screener (frozen, computed once per weekly rebalance boundary,
point-in-time — only data strictly before the as-of day is used, signals at
day *t* earn from *t+1*):

```
exclude      = BTC, ETH, and fiat/stable quote pairs
               (USDC/BUSD/FDUSD/TUSD/EUR/GBP-style). Thesis = less-efficient alts.
qualify      = (trailing-30d mean quote_volume ≥ USD 20M)         # liquidity floor
             AND (first daily bar ≥ 90 days before as-of)          # listing-age floor
metric       = ratio_t = quote_volume_t / median(quote_volume over trailing 30d)
               # computed from fetch_daily_klines DailyRow.quote_volume (uni1d_* cache).
               # NOTE: the OHLCV cache Candle.volume is BASE-coin volume, NOT quote —
               # the uni1d_ daily klines are the only correct source.
select       = rank qualifiers descending by metric_t, take top_n. Membership governs
               NEW-ENTRY eligibility only; open positions run to the engine's own
               trailed-stop exit (exits stay fixed, no forced close on dropout).
rebalance    = weekly (every 7 days), mirroring xsection/breadth convention.
```

Treatment grid (each cell = one treatment spec; engine + cost + window fixed,
only the screener varies):

- **`volexp_top5_30d_ratio`** — `{top_n:5,  lookback:30d, metric:ratio}`  *(the core rule)*
- **`volexp_top5_60d_ratio`** — `{top_n:5,  lookback:60d, metric:ratio}`
- **`volexp_top10_30d_ratio`** — `{top_n:10, lookback:30d, metric:ratio}`
- **`volexp_top5_30d_zscore`** — `{top_n:5,  lookback:30d, metric:zscore}`

**Treatment grid = 4 specs. `n_trials = 4`** for the DSR multiple-comparison
correction.

Control (gating — same exchange, engine, params, cost, funding, window,
rebalance cadence, total gross; only the selection rule differs):

- **`static_basket`** — all qualifiers (liquidity + age floors identical to the
  treatment), **equal-weight, no expansion ranking**. Same total gross `G=1.0`
  divided across the `N` qualifiers (`f_slot = G/N`). Isolates whether the
  *volume-expansion selection* adds edge beyond naïve broad alt exposure.

Reference (non-gating — reported alongside, not a promotion trial):

- **`btc_deployed`** — the byte-identical deployed engine on `BTC/USDT 4h`
  (`long_only=True`, the actual deployed config) over the same window. The
  decayed baseline; reported so "absolute revival" is visible. Excluded from
  `n_trials` and from the dominance gate.

Control and reference are evaluated for the dominance/reporting checks but are
**not** promotion trials and are excluded from `n_trials`.

## 3. Treatment vs control (the dominance gate)

Each treatment spec is paired against the **`static_basket` control** — holding
the exchange, engine, params, cost, funding, rebalance cadence, total gross,
and the screen/holdout/lockbox splits identical. Only the **universe selection
rule** differs (expansion-ranked top-N vs equal-weight all-qualifiers). A
treatment spec is eligible for promotion only if it **strictly dominates the
control on both portfolio MAR and portfolio Sharpe** at holdout, at the
walk-forward aggregate, and at the lockbox tail. This operationalizes the
program thesis ("volume-expansion selection revives edge") as a falsifiable,
paired comparison. (The `static_basket` control and `btc_deployed` reference
are excluded from `n_trials`; they are baselines, not promotion seekers.)

## 4. Evaluation (hybrid ladder + walk-forward + control dominance)

Reuses `research/ladder.py` stage semantics and the bespoke-runner pattern
(`orderflow_runner` / `voltarget_runner`). The **frozen ladder constants are
NOT mutated** (`SCREEN_FRACTION=0.7`, `SCREEN_MIN_TRADES=30`,
`DSR_THRESHOLD=0.95`, `LOCKBOX_MIN_MAR=1.0`, `LOCKBOX_MIN_TRADES=10`,
`DRAWDOWN_BUDGET=-0.30`, `R_SANITY_CAP=20.0`) so concluded domains' DSR
calibration is untouched. The single adaptation is that MAR / Sharpe / maxDD
are computed on the **portfolio daily equity curve** (`equity_summary_from_returns`),
while trade-count / expectancy_R are pooled across the underlying per-symbol
Donchian trades.

- **Stage 1 — screen (first 70% of the research window):** pooled underlying
  Donchian trades across all selected symbols/positions ≥ `SCREEN_MIN_TRADES`
  (30) **and** pooled `expectancy_R > 0`.
- **Stage 2 — holdout (remaining 30% of research):** portfolio `MAR > 0`
  **and** portfolio `max_drawdown ≥ DRAWDOWN_BUDGET (−0.30)`.
- **Stage 3 — DSR:** `deflated_sharpe ≥ DSR_THRESHOLD (0.95)` with
  `grid_size = n_trials = 4` (trial-Sharpe variance across the 4 treatment
  specs' portfolio research Sharpes; screened-out specs still deflate).
- **Stage 3.5 — walk-forward:** rolling, **1-year warm-up / 6-month test /
  6-month step** at 4h (non-overlapping; construction frozen, no param
  selection — the warm-up is an offset, not a train-fit). Universe rebuilt
  daily-within-fold from trailing data only (causal by construction). Requires
  `≥ 1 fold`, treatment aggregate portfolio MAR > 0, **and** dominance over
  the control on MAR & Sharpe.
- **Stage 4 — one-touch lockbox (final 20%, fence opened once):**
  `tail_mar ≥ LOCKBOX_MIN_MAR (1.0)`, `tail_trades ≥ LOCKBOX_MIN_TRADES (10)`,
  `tail_drawdown ≥ −0.30`, **and** dominance. The lockbox is opened only after
  a spec has survived stages 1 → 2 → 3.5 → DSR.
- **Dominance** (cross-cutting): treatment portfolio > control portfolio on
  MAR **and** Sharpe at holdout, WF aggregate, and lockbox tail.

## 5. Decision

- → **PAPER-LIVE WATCHING** iff **at least one treatment spec** clears stages
  1, 2, 3.5, DSR, **and** 4, **and** strictly dominates its `static_basket`
  control at holdout, WF aggregate, and lockbox tail. The promoting screener
  configuration alone goes to watch; the others are closed. The `btc_deployed`
  reference numbers (notably its 2025–2026 tail) are reported with the verdict
  so "absolute revival vs the decayed engine" is on the record.
- → **CLOSED NEGATIVE** otherwise.

**Kill rule (pre-committed, no rescue):** on a closed-negative verdict there
is **no v2 universe rule, no added/relaxed filter, no long-only flip, no
exit-ratio tuning, no top-N re-tuning**. The universe-expansion lever is
terminal for the frozen Donchian engine on a closed-negative verdict.
`n_trials = 4`.

## 6. Data, history window, and coverage

- Perp enumeration: `research.universe_data.list_um_perp_symbols()` — walks the
  Binance Vision S3 archive, **includes delisted symbols** (survivorship-clean;
  ccxt `load_markets` would miss them). Verified present: LUNA/LUNA2, etc.
- Daily 24h quote volume: `fetch_daily_klines(symbol, start, end, cache_dir)` →
  `list[DailyRow(ts_ms, close, quote_volume)]`, cached at
  `.backtest_cache/uni1d_{SYMBOL}.csv` (729 files already present). This is the
  **only** correct source for the expansion metric (OHLCV `Candle.volume` is
  base-coin volume, not quote).
- Engine candles + funding: `fetch_perp_candles(symbol, "4h", start, end,
  cache_dir)` and `fetch_funding_rates(symbol, start, end, cache_dir)`, both
  fapi-served and delistent-inclusive.
- Listing age: derived from the first available daily bar (`rows[0].ts_ms`);
  no exchange `onboardDate` field exists or is used.
- Window: **`UNIVERSE_DONCHIAN_START_MS = 1_609_459_200_000` (2021-01-01 UTC) →
  run date** (~5.5 yr). `LOCKBOX_FRACTION = 0.2` → fence ≈ 2025-05.
- Coverage: a symbol is rankable on day *t* only if it has ≥ `lookback` days of
  quote-volume history and ≥ 90 days of age strictly before *t*; otherwise it
  is absent from that day's qualifier set (no forward-fill, no lookahead).
- Delisting: a delisted symbol simply stops producing daily rows after its last
  trading day; it stays rankable up to its last bar then drops out. A position
  open at delisting is marked to the last available 4h close (no survivorship
  leakage; the universe enumeration already includes the delisted history).

## 7. Runner architecture (reuses the bespoke domain-runner pattern)

Mirrors `src/moonface/research/orderflow_runner.py`:

- `src/moonface/research/universe_donchian.py` — frozen screener
  (`screen_universe(daily, asof, spec) -> list[str]`, adapting
  `xsection.build_universe` to rank by expansion ratio), the bar-by-bar
  mark-to-market **portfolio simulator**
  (`simulate_portfolio(membership, per_symbol_trades, candles, funding, gross)
   -> PortfolioCurve` with `.daily_returns` and `.pooled_trades`), the 4
  treatment specs + `static_basket` control + `btc_deployed` reference, and the
  dominance evaluators (`evaluate_dominant`, `lockbox_dominant`, `stage1_of` /
  `stage2_of` / `stage4_of` on the portfolio curve).
- `src/moonface/research/universe_donchian_wf.py` — rolling walk-forward
  (`walk_forward_paired`-style with 1yr/6mo/6mo at 4h) + `stage35` dominance
  check on the portfolio curve; mirrors `orderflow_wf.py`.
- `src/moonface/research/universe_donchian_runner.py` — `register(store,
  now_ms)` (freeze window + fence + insert the 4 treatment specs, the control,
  and the reference) and `run_domain(store, loader, out_root) ->
  "closed_positive" | "closed_negative"` (drives stages 1→2→3.5→DSR→4 with
  portfolio-curve metrics + control dominance; writes
  `experiments/research/universe_donchian/verdict.md`).
- `tools/research.py` — new `universe-donchian` subcommand (register + run),
  mirroring the `orderflow` subcommand.
- Config: `{"runner": "universe_donchian", ...}` so the generic `runner.run`
  skips this domain (the bespoke guard already in place for voltarget/orderflow).
- Reuses unchanged: `Store` (registration + one-touch lockbox), `FencedBundle`,
  `ladder.evaluate_research` / `evaluate_lockbox` / `stage*_passed` /
  `stage3_dsr`, `trend_sim.simulate_donchian` + `TrendParams` (deployed),
  `universe_data.list_um_perp_symbols` / `fetch_daily_klines` /
  `fetch_perp_candles` / `fetch_funding_rates`, `xsection.build_universe`,
  `equity_summary_from_returns`, `deflated_sharpe`, `COST_FRACTION`.

## 8. Run

```
python tools/research.py universe-donchian
```
