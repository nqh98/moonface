# Free-Data Feasibility Report — Binance Vision `aggTrades` for Aggressor-Trades Rung-0

**Date:** 2026-06-18
**Scope:** Determine whether a FREE/PUBLIC datasource can replace the `ExampleVendor`
placeholder for the frozen `aggressor_trades` Rung-0 cycle, without paid providers or
manually-supplied proprietary CSVs. Answers the seven required questions. **No data was
staged for the experiment, no run was executed, no lockbox was touched** in producing this
report. The only data downloaded was a single 5.2 MB public file (2020-01-07) used to
empirically confirm the schema, then deleted.

---

## Bottom line up front

1. **A free/public source exists and satisfies the schema:** Binance Vision USDⓈ-M futures
   daily `aggTrades` (MIT-licensed, public S3/CloudFront, no API key) reproduces the
   preregistered `ts_ms, symbol, side, price, size` schema exactly, with `side` inferred
   unambiguously from `is_buyer_maker`. ≥180 days (in fact ~6.5 years) of BTCUSDT is
   available and reproducible from source. (Q1–Q5: YES.)

2. **BUT it is NOT genuinely new information as the cycle is frozen.** The frozen feature
   `imbalance = (buy_vol − sell_vol)/(buy_vol + sell_vol)` at 5 min is a **monotonic,
   rank-identical transform** of `sum_taker_long_short_vol_ratio` — the exact input series
   the repo ALREADY tested as `taker_flow_momentum`, which the repo's own docstring calls
   *"aggressive (taker) volume imbalance"* and which was verdict **`mechanism_does_not_exist`**.
   (Q6: NO, not new at the feature level.)

3. **Therefore the preregistration's "genuinely new data" justification does not hold
   as written** and the cycle as-frozen is at risk of being a re-skin of an already-failed
   family — in tension with the prereg's own *“must not reuse failed free-data families
   under a new name”* clause. A decision is required before any staging/run. (Q7: amendment
   or re-scope required; three options below.)

---

## Method / evidence base

- **Official schema:** Binance's MIT-licensed `binance/binance-public-data` repo (FUTURES →
  AggTrades table).
- **Empirical download:** `BTCUSDT-aggTrades-2020-01-07.zip` (5,167,047 bytes, HTTP 200)
  from `https://data.binance.vision`. First rows inspected directly (see Q4).
- **REST semantics:** public `/fapi/v1/aggTrades?symbol=BTCUSDT` sample confirms field
  meanings (`a`=aggId, `p`=price, `q`=qty, `T`=time ms, `m`=isBuyerMaker).
- **Availability/history:** HTTP HEAD probes across 2019→2026.
- **Codebase audit:** grep + read of the repo's prior taker/aggressor usage (file:line below).

---

## Q1 — Which free/public datasource will be used?

**Binance Vision USDⓈ-M futures daily `aggTrades`** for `BTCUSDT`:

```
https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-YYYY-MM-DD.zip
```

- Public Amazon S3 / CloudFront bucket. **No login, no API key, no paid tier.** MIT-licensed.
- This repo already fetches four other families from the same bucket
  (`src/moonface/backtest/universe_data.py` klines+funding, `metrics_data.py` 5-min
  OI/positioning/taker ratios, `bookdepth_data.py` depth) — an `aggTrades` fetcher follows
  established precedent.
- Equivalent fallback: futures daily `trades` (raw individual fills, also has `isBuyerMaker`).
  **`aggTrades` is recommended**: it is the canonical aggressor-flow file, smaller, and its
  per-row `is_buyer_maker` gives the aggressor side directly.

`ExampleVendor` was only a synthetic placeholder from the readiness dry-run; this report maps
it to the real free source above.

## Q2 — Reproducible from source, without manual proprietary files?

**Yes.** Empirically demonstrated while writing this report:

- Stable, deterministic HTTPS URLs (path-parameterized by symbol + date).
- Each zip has a sibling `.CHECKSUM` (sha256) for integrity — verified present (HTTP 200) for
  `BTCUSDT-aggTrades-2024-01-01.zip.CHECKSUM`.
- `curl`/`wget` only; helper download scripts ship in `binance/binance-public-data`
  (`python/`, `shell/`).
- No proprietary/manual file is required at any step. A future staging script downloads
  N daily zips, verifies checksums, concatenates, and emits the 5-column CSV — fully scripted.

## Q3 — At least 180 days of BTCUSDT futures data?

**Yes — far more.** HTTP HEAD probes (`HTTP 200` = present):

| Date | Status | Size |
|---|---|---|
| 2019-09-01 | 404 | (pre-inception; USDⓈ-M futures launched 2019-09) |
| 2020-01-01 | 200 | 1.0 MB |
| 2020-01-07 | 200 | 5.2 MB |
| 2020-09-01 | 200 | — |
| 2022-06-01 | 200 | 24.6 MB |
| 2024-01-01 | 200 | 10.1 MB |
| 2025-12-01 | 200 | 36.7 MB |
| 2026-06-17 | 404 | (not yet posted — Vision publishes daily files the *next* day) |

So BTCUSDT aggTrades run from **≈2020-01 through present (~6.5 years)**. The 180-day and the
prereg's 365-day minimums are trivially satisfied. Sizing note for staging: compressed daily
files range ~1 MB (quiet early days) to ~37 MB (recent busy days); a 365-day window is on the
order of several GB compressed — staging needs disk but is manageable (one-touch ingest already
handles coverage/monotonicity/duplicate audits per the readiness gate).

## Q4 — Can it produce the exact preregistered schema?

**Yes.** Empirically confirmed schema (the file is **headerless**; first real rows from
2020-01-07):

```
19427029,7757.74,2.277,26733068,26733069,1578355200249,true
19427030,7757.68,0.626,26733070,26733070,1578355200250,true
19427031,7757.35,0.260,26733071,26733072,1578355200250,true
```

Column order (per official docs, matches the empirical rows): **`aggregate_trade_id, price,
quantity, first_trade_id, last_trade_id, timestamp_ms, is_buyer_maker`**.

Mapping to the preregistered `ts_ms, symbol, side, price, size`:

| Prereg field | Source | Notes |
|---|---|---|
| `ts_ms` | col 6 `timestamp` | milliseconds (13 digits); matches `ts_ms` directly |
| `price` | col 2 `price` | direct |
| `size` | col 3 `quantity` | BTC base-asset units for BTCUSDT perp |
| `symbol` | **injected from file path** | `BTCUSDT` — not a column in the file (per-symbol files) |
| `side` | **derived from col 7 `is_buyer_maker`** | see Q5 inference rule |

All five fields are producible. `symbol` and `side` are deterministic derivations, not
fabrications.

## Q5 — Missing fields or assumptions? (incl. explicit aggressor-side inference)

**Aggressor-side inference (the load-bearing assumption — documented here as required):**

Binance records `is_buyer_maker` = "was the buyer the maker?" The aggressor (taker) is the
side that crossed the spread:

- `is_buyer_maker = False` → buyer is the **taker** → aggressor is the **buyer** → `side = buy`
- `is_buyer_maker = True`  → buyer is the **maker** → counterparty seller is the taker → `side = sell`

This is the standard, unambiguous mapping (confirmed by Binance's glossary and the REST `m`
field; `m=false` row in the API sample ⇒ buy-aggressor). It is a 1-bit deterministic transform
of a native field — no data is invented.

**Other assumptions to document in any amended prereg:**

- **`symbol` is path-derived, not a column.** Deterministic; the staging step adds it.
- **"Trade print" = aggregated trade, not raw fill.** Binance collapses same-price /
  same-taker-side fills within ~100 ms into one `aggTrade` row whose `quantity` is the sum.
  For a *volume* imbalance this is exact. If truly raw individual fills are required, use the
  `trades` files (same `isBuyerMaker` field) instead. Minor; does not affect imbalance.
- **Timestamp unit is milliseconds (futures).** (Only SPOT switched to microseconds from
  2025-01-01; USDⓈ-M futures remain milliseconds.) Matches `ts_ms`.
- **`size` unit:** base-asset BTC quantity (document per prereg "base or contract units").
- **Forbidden-field cleanliness:** aggTrades contain ONLY trade fields — no returns, alpha
  scores, funding, basis, OI, liquidation, or order-book fields. Consistent with the prereg's
  forbidden set. ✓

## Q6 — Is this genuinely new information vs already-used OHLCV/funding/OI/book-depth?

**No — not at the level of the frozen feature. This is the report's key finding.**

The repo has **already tested aggressor/taker volume imbalance**, and it failed:

- `src/moonface/backtest/edge/positioning_signals.py:12` (module docstring) explicitly says:
  *"taker_flow_momentum: aggressive (taker) volume imbalance is informed urgency."*
- `make_taker_flow_momentum` (`positioning_signals.py:114-116`) consumes a feature series
  that the loaders map to **`sum_taker_long_short_vol_ratio`**
  (`tools/drift_screen_multifamily.py:58`, `src/moonface/research/pathsig/baseline.py:75`,
  `src/moonface/research/domains.py:87-89`, `src/moonface/backtest/metrics_data.py:25`).
- That metric is Binance's `takerLongShortRatio` — the **taker (aggressor) buy/sell base-volume
  relationship per 5-minute interval** (`buySellRatio = buyVol/sellVol`, plus components).
- Drift-screen verdict (`experiments/drift_screen_multifamily/leaderboard.md:9`):
  `taker_flow_momentum {window:180, z_thr:1.5}` → **`mechanism_does_not_exist`** (effect
  column ≈ −0.004, essentially zero aggregate drift).

**Why the frozen Rung-0 feature is the same information:**

- Binance ratio `r = buyVol/sellVol` per 5 min.
- Frozen Rung-0 feature: `imbalance = (buy_vol − sell_vol)/(buy_vol + sell_vol) = (r − 1)/(r + 1)`.
- `(r−1)/(r+1)` is a **strictly monotonic, one-to-one transform** of `r` on `r > 0`.
- Therefore `imbalance` and `sum_taker_long_short_vol_ratio` have **identical rank ordering**.
- Rung-0's primary statistic is a **Spearman rank IC** of `imbalance[t] → return[t+1]` — and
  Spearman IC is invariant under monotonic transform. So the rank-IC test on `imbalance` is
  numerically the same test one would run on the already-tested taker ratio.

**What actually differs (real, but not "new information"):**

- *Statistic/framing:* `taker_flow_momentum` used a 180-period rolling **z-score ± 1.5σ event
  threshold** (drift screen); Rung-0 uses the **raw 5-min level** via rank-IC + Newey-West t +
  5-bucket monotonicity (information test).
- *Cadence/horizon:* the drift screen operated on a 4 h-universe with the 5-min metric
  as-of-joined; Rung-0 is native 5-min → next-5-min.

These are methodological differences, not a new signal family.

**What WOULD be genuinely new (only if the feature is changed):** raw trade-level data enables
features the binned ratio *cannot* produce — trade-**size distribution**, large-block ("whale")
aggression vs retail, print-**count / hit-rate**, sub-5-min microstructure timing. The prereg
even gestures at this with its "top 1% largest trade-size" robustness trim. **But the frozen
feature discards this advantage**: it sums `size` into bucket volume, collapsing back to exactly
what the binned taker ratio already provides.

*Side note:* `taker_z` in the distributional-path program is a misnomer —
`src/moonface/research/pathsig/dataset.py` computes it as a z-score of the **open-interest**
series (shares the `oi` array), not aggressor imbalance. So that program did **not** test
aggressor imbalance; the drift-screen `taker_flow_momentum` is the relevant prior test, and it
failed.

## Q7 — Amend the preregistration before freezing, or is it compatible as-is?

**As frozen, it is NOT compatible with a "genuinely new data" justification.**

The prereg's *New-Data Confirmation* (`AGGRESSOR_TRADES_RUNG0_PREREGISTRATION.md`, lines 159–169)
claims the feature *"depends on `side` and trade-level `size`, neither of which exists in the
failed free-data families."* That claim is **contradicted by the codebase**:

- The `side` (aggressor direction) information **does** exist in a failed family — it is
  precisely what `taker_flow_momentum` / `sum_taker_long_short_vol_ratio` encodes.
- Trade-**level** `size` is genuinely absent from the binned ratio — but the frozen feature
  does not use it as a feature (it only sums it), so that distinction is moot as frozen.

Consequently, running the cycle as-frozen risks violating the prereg's own clauses:
- Context: *"must not reuse failed free-data families under a new name."*
- Kill Rule: *"No … feature family expansion … to make the result look better"*
  and *"requires any unregistered feature … alternate universe … to make the result look better."*

**Three options for the human to decide (no staging/run until chosen):**

- **(A) AMEND to be genuinely new.** Change the feature to exploit information the binned ratio
  cannot provide — e.g. *large-print* imbalance (imbalance computed only from the top-X% largest
  aggTrades), *size-weighted-vs-count-weighted* imbalance divergence, or *print-rate/arrival*
  signals. Re-freeze a new prereg with a new hypothesis statement. Then the raw `aggTrades`
  source is justified and the cycle is genuinely new.
- **(B) RE-FRAME honestly as a re-test, not "new data."** Keep the frozen feature but strike the
  "genuinely new data" claim; state explicitly that this is a *finer-grained, different-statistic
  (raw rank-IC vs z-threshold) re-examination of the aggressor-imbalance family at 5-min*, and
  decide whether that replication is worth spending a one-touch lockbox cycle given the prior
  `mechanism_does_not_exist` verdict.
- **(C) DO NOT RUN.** Treat the frozen feature as a re-skin of a failed family and leave the
  aggressor-imbalance family closed. Consistent with the program's standing conclusion that this
  family is dead.

---

## Recommendation (human-gated)

Do **not** stage data or run the sealed cycle as-frozen. The free source is feasible and clean
(Q1–Q5), but the cycle is not genuinely new as written (Q6) and the prereg must be amended or
re-scoped (Q7). The human should choose **(A)**, **(B)**, or **(C)** above before any further
action. No lockbox is touched at any point.

---

## Appendix — evidence index

- Official schema + license (MIT): `https://github.com/binance/binance-public-data` (FUTURES → AggTrades / Trades tables; CHECKSUM section).
- Empirical sample rows: `BTCUSDT-aggTrades-2020-01-07.zip` (downloaded 2026-06-18, then deleted).
- REST semantics: `https://fapi.binance.com/fapi/v1/aggTrades?symbol=BTCUSDT&limit=2` → `{"a":…,"p":"65941.10","q":"0.012","T":1781717430927,"m":false,…}`.
- Prior art in repo:
  - `src/moonface/backtest/edge/positioning_signals.py:12` (docstring), `:114-116` (`make_taker_flow_momentum`).
  - `src/moonface/backtest/metrics_data.py:25` (`sum_taker_long_short_vol_ratio`).
  - `tools/drift_screen_multifamily.py:58`, `src/moonface/research/domains.py:87-89`, `src/moonface/research/pathsig/baseline.py:75`.
  - `experiments/drift_screen_multifamily/leaderboard.md:9` (verdict `mechanism_does_not_exist`).
  - `src/moonface/research/pathsig/dataset.py` (`taker_z` = OI z-score, misnamed — not imbalance).
