# Free-Data Feasibility: Fiat-Onramp Stablecoin Micro-Peg (USDT/USD, USDC/USD)

Date: 2026-07-09. Scope: readiness/data-quality ONLY (Lane 2 of
docs/new_research_lanes.md). No signal design, no premium indicator, no BTC
test, no alpha work. Mirrors experiments/newdata/FREE_DATA_FEASIBILITY_etf_flows.md
and _deribit_options.md.

## Requirement

Fiat-quoted (NOT stable-to-stable) USDT/USD and USDC/USD, <=1-minute bars with
volume, >=180 days history (multi-year preferred), coverage >=0.95, monotonic
timestamps, keyless collection, research/derived/retention-clean license. Probe
tool: tools/recon_stablecoin_peg.py (`probe`).

## Findings

**Q1. Does the data exist publicly?** PARTIAL. Kraken public AssetPairs exposes
both required fiat pairs: `USDTZUSD` and `USDCUSD`. Coinbase Exchange exposes
`USDT-USD` publicly, but `USDC-USD` returned HTTP 404 in the live probe on
2026-07-09.

**Q2. Is history machine-collectable keylessly? (THE CRUX)**
- Kraken OHLC: 721 bars / 12.0h per request at `interval=1`, confirming the
  hard short-window cap; not a viable history path by itself.
- Kraken Trades cursor: 1000 trades / 135.76m on the first `USDTZUSD` page.
  Reissuing with `since=<last>` did not walk backward: the second response was
  a 1-trade forward edge (`older_than_page1=False`). So the public Recent
  Trades endpoint is not a usable backfill cursor for 180d minute history.
- Coinbase candles: the default live `USDT-USD` probe returned 350 bars /
  5.8h. A bounded historical request for 2026-01-10 00:00 UTC to 2026-01-10
  05:00 UTC returned 301 one-minute bars, proving minute candles are reachable
  at the 180-day mark for `USDT-USD`. But `USDC-USD` is absent, and a 180-day
  `USDT-USD` backfill still costs about 864 five-hour requests.
- Verdict: **not collectable** for the required two-pair scope. One pair
  (`USDT/USD`) is partly keyless-collectable via Coinbase time-walks; the full
  `(USDT/USD, USDC/USD)` requirement is not.

**Q3. Data quality.** On the live Coinbase `USDT-USD` snapshot: coverage 1.0,
gaps 0, monotonic False (endpoint returns newest-first order). Premium is
measurable and non-flat: mean -9.364 bps, range -11.5 to -8.0 bps, 0 peg
crosses over the snapshot. Liquidity sanity: all bars carried volume = True.

**Q4. License.** On their face, both venues document unauthenticated public
market-data access. Kraken documents public REST rate limits via a call-counter
model; Coinbase documents public candle endpoints and public-IP rate limits.
That clears the "keyless access exists" question, but this memo does **not**
clear downstream retention/redistribution terms by legal review. Treat the
license verdict as "research use looks plausible, retention-clean not fully
adjudicated."

**Q5. Would forward collection help?** YES, but only as a slow fallback. A
forward minute collector could accumulate a clean internal `USDT/USD` and
Kraken `USDC/USD` series over time, but it does not satisfy the immediate
>=180-day gate and would require recurring human ops.

**Q6. Schema fit.** The existing Binance `data.py` H1/H4/D1/W1 OHLCV store does
not cover these fiat-stablecoin minute pairs. Any design that clears this gate
needs a new lightweight minute-bar store or a dedicated exogenous data class.

## Conclusion - BLOCKED at Stage 0

The gate fails on history collectability for the required scope. Kraken does
list both fiat pairs, but its free OHLC endpoint only gives ~12h and its Recent
Trades cursor does not page backward. Coinbase gives a usable minute-history
walk for `USDT-USD`, but `USDC-USD` is absent as of 2026-07-09. That means the
two-pair free-data requirement is not met today.

Honest options, human-gated:
- A keyed/paid venue or commercial historical feed that serves both fiat pairs
  at 1-minute resolution.
- Forward collection with recurring ops cost, accepting a 180-day wait before
  the lane can even be reconsidered.
- Close Lane 2 at Stage 0 under the current free-data mandate.

No provider registration is frozen here; no alpha preregistration exists.

**Decision (2026-07-09): Option C — Lane 2 CLOSED at Stage 0** under the current
free-data mandate. The recon tool and this memo remain as the reusable record;
reopening requires a paid/keyed both-pair feed (A) or a completed forward
collection (B), either of which needs a NEW pre-registration.

Probes: tools/recon_stablecoin_peg.py probe (2026-07-09), plus a Kraken Recent
Trades cursor check and a Coinbase `USDT-USD` 2026-01-10 candle walk-back check
run in terminal for Q2.
