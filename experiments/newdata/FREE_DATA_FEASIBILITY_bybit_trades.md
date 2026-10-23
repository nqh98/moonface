# Free-Data Feasibility Report — Bybit public trades for 15m Aggressor-Delta / Q-Sweep

**Date:** 2026-07-07
**Scope:** Determine whether Bybit's free/public trade data can serve as the
microstructure-flow source for the 15m Q-Sweep Aggressor-Delta logic, after
Hyperliquid's REST snapshot proved too small (`tools/recon_hl.py`: `recentTrades` returns
~10 prints ≈ 1.2 s) and the Binance Vision `aggTrades` path was closed
(`FREE_DATA_FEASIBILITY_binance_aggtrades.md`, aggressor-trades lane KILLED 2026-07-03).
Answers the seven required questions. **No experiment was staged, no run executed, no
lockbox touched.** The only data downloaded was a single public REST snapshot and one
public daily archive file (2026-07-06), used to confirm schema, then discarded.

---

## Bottom line up front

1. **A free/public Bybit source exists and is a clean Binance-Vision-class archive.**
   `public.bybit.com/trading/BTCUSDT/` publishes **2,295 daily full-tick `.csv.gz`
   files, 2020-03-25 → 2026-07-06, keyless** (2.92 M BTCUSDT trades on 2026-07-06 in a
   single 101 MB file). Taker `side` is given directly (`Buy`/`Sell`). Access,
   history, and schema are all fine. (Q1–Q5: YES.)

2. **BUT at the feature level it is NOT genuinely new information.** The only usable
   historical field is net taker imbalance from `side` — the **same feature family**
   the repo already tested as `taker_flow_momentum` (Binance taker flow) with verdict
   **`mechanism_does_not_exist`**, and the aggressor-trades lane it fed was closed
   2026-07-03. A venue swap (Binance→Bybit) of an already-killed feature does not by
   itself clear the "genuinely new data" bar. (Q6: NO as-scoped.)

3. **The two fields that COULD be genuinely new are unavailable or empty in the free
   archive.** `RPI` (retail-price-improvement flag — would separate retail from
   non-retail aggressor flow) is present in the schema but **all zeros** in the
   historical dump (2,924,235/2,924,235 = `0`). `isBlockTrade` (large negotiated flow)
   appears only in the **live** REST/WS feed, not in the archive. `tickDirection` is a
   deterministic function of the price path the repo already holds. (Q6 differentiators:
   none survive on free historical data.)

4. **Verdict: do NOT open a backtest lane on the Bybit free archive as a new edge.** It
   is a data-source upgrade for a closed mechanism, not new information. The only
   genuinely-new angle (RPI / block-flow) exists solely in the *live* feed and would
   require forward-collection (à la the Deribit chain collector) plus a sparse-event
   power argument before it is testable. (Q7: KILL as-scoped; one narrow forward-collect
   option noted, human-gated.)

---

## Method / evidence base

- **Live REST probe:** `GET https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=1000`
  → `retCode 0`, 1000 trades spanning **19.0 s** (2026-07-07 15:55:59 → 15:56:18 UTC),
  aggressor delta −12.88 BTC. Sample row:
  `{"execId":…,"price":"63910.00","size":"0.027","side":"Sell","time":"1783439778672","isBlockTrade":false,"isRPITrade":false,"seq":"665509832019"}`.
- **Historical archive probe:** `https://public.bybit.com/trading/BTCUSDT/` index lists
  2,295 `.csv.gz` files. Downloaded `BTCUSDT2026-07-06.csv.gz` (101,585,926 bytes),
  2,924,236 rows incl. header.
- **Repo audit:** prior taker-flow lineage — `taker_flow_momentum`
  (`mechanism_does_not_exist`); aggressor-trades lane KILLED 2026-07-03
  (`aggtrades-hawkes-results`); Binance aggTrades Q6 failure
  (`FREE_DATA_FEASIBILITY_binance_aggtrades.md`).

---

## Q1 — Which free/public datasource will be used?

**Bybit public daily trade archive** (primary):

```
https://public.bybit.com/trading/BTCUSDT/BTCUSDT{YYYY-MM-DD}.csv.gz
```

Public bucket, **no login / no API key / no paid tier**. Live REST
(`/v5/market/recent-trade`, `limit≤1000`) and the public WS `publicTrade.BTCUSDT`
stream are the live-tape counterparts.

## Q2 — Does it reproduce the required schema?

**YES, and richer than Binance.** Archive header (verified):

```
timestamp, symbol, side, size, price, tickDirection, trdMatchID,
grossValue, homeNotional, foreignNotional, RPI
```

`side` ∈ {`Buy`,`Sell`} is the **taker/aggressor** side directly (no `isBuyerMaker`
inversion needed). Aggressor Delta = Σ size·(+1 if Buy else −1).

## Q3 — Is there enough history?

**YES.** 2,295 daily files, 2020-03-25 → 2026-07-06 (~6.3 years), ≈1-day publish lag.
Far exceeds any ≥180-day requirement.

## Q4 — Is it reproducible from source?

**YES.** Static daily archive files, deterministic content; 2.92 M trades/day for BTC.
`grossValue`/`homeNotional`/`foreignNotional` are `price·size` restatements.

## Q5 — Access cost / rate limits?

**Trivial.** Direct HTTPS file GETs, no key, no rate ceiling of concern. One BTC day is
~100 MB gz; a multi-year pull is bandwidth-bounded, not access-bounded.

## Q6 — Is it genuinely NEW information? (the gate)

**NO, as-scoped.** Decompose the archive fields:

| Field | New vs repo's existing data? | Why |
|-------|------------------------------|-----|
| `side` (taker imbalance) | **No** | Same family as `taker_flow_momentum` → `mechanism_does_not_exist`; aggressor lane closed 2026-07-03. Venue swap only. |
| `price`,`size`,`grossValue`,`homeNotional`,`foreignNotional` | No | Already have price/volume; notionals are `price·size`. |
| `tickDirection` | No | Deterministic function of the price path the repo already holds. |
| `RPI` (retail flag) | *Would be* — but **empty** | All `0` across 2,924,235 rows in the archive → carries zero information as delivered. |
| `isBlockTrade` | *Would be* — but **absent** | Only in the live REST/WS feed, not in the free archive. |

The single field that could make Bybit flow genuinely different from the already-failed
Binance taker flow (`RPI` retail separation) is **not populated in the free historical
data**. Therefore the archive is a re-skin of a closed feature family — exactly the
condition the Binance memo's Q6 warned against.

## Q7 — Decision

**KILL the backtest-archive route.** Do not stage a lane; it reruns a closed mechanism
on a new venue with no new information.

**One narrow, human-gated forward option (not recommended without a power case):** the
`RPI` and `isBlockTrade` flags DO appear in Bybit's **live** REST/WS feed. Separating
retail (`isRPITrade`) or block (`isBlockTrade`) aggressor flow from the rest is the only
plausibly-new hypothesis. It would require:
- a forward-collector (Deribit-chain-collector pattern; human ops cron), because the
  free archive zeros/omits these flags;
- a sparse-event power argument (RPI/block prints are a small, possibly-rare subset);
- a pre-registration that explicitly states why venue-conditioned retail/block flow is
  new information the killed Binance taker family did not contain.

Absent that pre-registration and power case, the recommendation is **WAIT** — no new
lane. Bybit is confirmed as the best *free tick-data source* available (superior to both
Hyperliquid REST and the retired Binance path) and should be recorded as such for any
*future, independently-motivated* microstructure hypothesis — but it does not resurrect
the aggressor-delta edge on its own.

---

## Relationship to `tools/recon_hl.py`

`tools/recon_hl.py` (Hyperliquid `recentTrades`) remains the working keyless snapshot probe
but is window-limited (~10 prints). Bybit REST (`limit=1000`) is larger but still only
~19 s of BTC perp — neither REST snapshot spans 15 min, so any *live* 15m Q-Sweep needs
a WS/polling accumulator regardless of venue. This memo concerns the *archive* route;
the live-accumulator route is a separate, still-open engineering question if a
mechanism ever justifies it.
