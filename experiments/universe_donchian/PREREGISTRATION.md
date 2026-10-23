# universe_donchian v1 — Pre-Registration

Frozen **2026-07-02, before any out-of-sample evaluation.** This file is the
immutable gate contract; it duplicates §1, §3, §4, §5 of
`docs/research-log/specs/2026-07-02-universe-donchian-design.md`. A changed
design requires a new experiment directory — this file is never edited after
the first OOS bar is read.

---

## 1. Hypothesis

On a **dynamic top-5 altcoin USDT-perp universe** (Binance USDⓈ-M, rebuilt
weekly from a survivorship-clean enumeration by **abnormal 24h quote-volume
expansion** with liquidity ≥ USD 20M trailing-30d-mean and listing-age ≥ 90-day
floors; BTC/ETH/stables excluded), the **frozen deployed Donchian breakout
engine** (`trend_sim.simulate_donchian`, `TrendParams(entry_n=40, trail_n=20,
atr_period=14, k_stop=2.0, long_only=False, funding_enabled=True)`, **4h**)
earns positive out-of-sample risk-adjusted return **and** strictly beats a
**static broad alt basket control** (same filters, equal-weight, no expansion
ranking) on MAR and Sharpe. The short side is enabled via the pre-existing
`long_only` flag; the entry/exit channel logic is byte-identical to the
deployed engine. BTC/USDT (the decayed deployed engine, 2025 −1.54R / 2026 YTD
−8.65R) is a non-gating absolute-revival reference.

The engine is frozen; v1 adds no new entry/exit code and no new data fetcher.

## 2. Treatment vs control (the one variable: the universe)

- **Treatment (n_trials = 4):** the frozen engine on the expansion-ranked universe.
  1. `volexp_top5_30d_ratio`  — `{top_n:5,  lookback:30d, metric:ratio}`
  2. `volexp_top5_60d_ratio`  — `{top_n:5,  lookback:60d, metric:ratio}`
  3. `volexp_top10_30d_ratio` — `{top_n:10, lookback:30d, metric:ratio}`
  4. `volexp_top5_30d_zscore` — `{top_n:5,  lookback:30d, metric:zscore}`
- **Control (gating):** `static_basket` — same engine/params/cost/funding/window/
  rebalance/total-gross, qualifiers identical, **equal-weight, no expansion
  ranking**.
- **Reference (non-gating):** `btc_deployed` — the byte-identical deployed engine
  on BTC/USDT 4h (`long_only=True`).

Each treatment is paired against the `static_basket` control; only the universe
selection rule differs. Promotion requires strict dominance on **both** portfolio
MAR and portfolio Sharpe at holdout, WF aggregate, and lockbox tail.

## 3. Evaluation (frozen hybrid ladder; ladder constants UNMUTATED)

MAR / Sharpe / maxDD on the **portfolio daily equity curve**
(`equity_summary_from_returns`); trade-count / expectancy_R pooled across
underlying per-symbol Donchian trades. `COST_FRACTION = 0.001` round-trip
(2× = 0.002 reported non-gating). Funding applied per position.

- **S1 screen (first 70% of research):** pooled trades ≥ 30 **and** expectancy_R > 0.
- **S2 holdout (30% of research):** portfolio MAR > 0 **and** maxDD ≥ −0.30.
- **S3 DSR:** deflated Sharpe ≥ 0.95, `grid_size = n_trials = 4`.
- **S3.5 walk-forward:** rolling 1yr warm-up / 6mo test / 6mo step @ 4h; ≥1 fold,
  aggregate portfolio MAR > 0, **and** dominance.
- **S4 lockbox (one-touch, final 20%):** tail portfolio MAR ≥ 1.0, tail trades
  ≥ 10, tail maxDD ≥ −0.30, **and** dominance.
- **Dominance (cross-cutting):** treatment > control on MAR **and** Sharpe at
  holdout, WF, lockbox.

Window: `START = 2021-01-01 UTC → run date`; `LOCKBOX_FRACTION = 0.2` (fence ≈
2025-05, overlapping the BTC-decay period). Universe rebuilt point-in-time
(trailing data only; signals at day *t* earn from *t+1*); survivorship-clean
(delisted symbols included in enumeration and history).

## 4. Decision + kill rule

- → **PAPER-LIVE WATCHING** iff ≥1 treatment spec clears S1→S2→S3.5→DSR→S4
  **and** strictly dominates the `static_basket` control at holdout, WF, and
  lockbox. The promoting screener alone goes to watch.
- → **CLOSED NEGATIVE** otherwise.

**Kill rule (pre-committed, no rescue):** on a closed-negative verdict — no v2
universe rule, no added/relaxed filter, no long-only flip, no exit-ratio tuning,
no top-N re-tuning. The universe-expansion lever is terminal for the frozen
Donchian engine. `n_trials = 4`.

## 5. Run

```
python tools/research.py universe-donchian
```
