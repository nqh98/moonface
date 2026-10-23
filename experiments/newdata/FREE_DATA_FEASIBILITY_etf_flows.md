# Free-Data Feasibility: US Spot Bitcoin ETF Daily Flows

Date: 2026-07-03. Scope: readiness/data-quality ONLY (candidate 2c of the
2026-07-03 research-director review, queued behind the Deribit collector
and the macro event-window study). No signal design, no data analysis, no
alpha work. Mirrors the structure of the Deribit and aggTrades docs.

## Requirement

Daily per-fund creation/redemption flows for the US spot BTC ETFs (IBIT,
FBTC, GBTC, ...) since launch (2024-01-11), machine-collectable under the
free-data mandate, with honest publication timestamps. Fits the existing
`macro_series` data class (`ts_ms, series_id, value, publish_lag_days`) —
no schema amendment needed. Gate: >= 180 days history (satisfied by the
~900-day series if collectable), coverage >= 0.95 of trading days,
monotonic timestamps, license permitting research/derived/retention.

## Findings

**Q1. Does the data exist publicly?** YES. Farside Investors
(farside.co.uk/btc/) publishes the canonical per-fund daily flow table
since 2024-01-11; issuers publish primary data (iShares IBIT product page
offers historical NAV + shares outstanding, from which flows are
derivable as d(shares) x NAV).

**Q2. Is it machine-collectable keylessly?** NO — this is the blocker.
- farside.co.uk: Cloudflare bot challenge (probe 2026-07-03 returned a
  5.6KB challenge page, no table).
- ishares.com product-data download endpoint: Akamai "Access Denied"
  (probe 2026-07-03).
- WebFetch/plain curl variants: 403 on both hosts.
- theblock.co / CoinGlass dashboards: bot-walled and/or paid API.
- SoSoValue: has an ETF-flow API with a free tier, but it is KEYED
  (registration + ToS) — outside the keyless precedent set by Binance
  Vision (MIT) and the Deribit public API, and redistribution/retention
  terms are not research-clean on their face.

**Q3. Timestamp integrity (the question that motivated this pass).**
Flows are published T+1 (after US close, often next morning); any future
design must consume them with `publish_lag_days >= 1`. The `macro_series`
schema already carries that field, so the gate can encode the lag honestly
— IF a collectable source existed.

**Q4. License.** Farside states no research/retention license; issuer data
is primary but access-controlled. Nothing here matches the license bar the
gate requires.

**Q5. Would forward collection help?** Not by itself — the block is
access, not history. Unlike Deribit (keyless API, missing history), here
the history exists but every free access path is bot-walled.

## Conclusion — BLOCKED at Stage 0, human decision required

No keyless free source satisfies the gate today. Honest options (choosing
is human-gated):

- **(A) Keyed free tier**: a human registers for a SoSoValue (or similar)
  free API key, reviews its ToS against the research/derived/retention
  bar, and a re-probe runs against the keyed endpoint.
- **(B) Human-in-the-loop collection**: a human periodically downloads the
  Farside/iShares files by browser; the lane pays a recurring ops cost and
  the coverage gate is at the mercy of that habit.
- **(C) Close the lane** at Stage 0 as access-infeasible under the
  free-data mandate.

No provider registration is frozen; no alpha preregistration exists. The
contemporaneity confound (flow chases same-day return) and the crowding
caveat from the review memo stand unexamined — they only matter if the
gate ever opens.

Probes: curl with browser UA against farside.co.uk/btc/ and the
ishares.com IBIT `.ajax` CSV endpoint, both 2026-07-03; WebFetch 403 on
farside.co.uk.
