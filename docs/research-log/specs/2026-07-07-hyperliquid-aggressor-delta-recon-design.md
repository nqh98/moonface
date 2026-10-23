# Hyperliquid Aggressor-Delta Recon — Design

**Date:** 2026-07-07
**Status:** Approved (design)
**Artifact:** `tools/recon_hl.py` (moved from the repo root in G0, 2026-08-22)

## Purpose

A one-shot, keyless reconnaissance probe of Hyperliquid's public tape that fetches
recent BTC trades and computes the **Aggressor Delta** (net taker flow) for the 15m
Q-Sweep logic. This tests Hyperliquid as the alternative microstructure-flow source
after the Binance Vision `aggTrades` path was retired
(`experiments/newdata/FREE_DATA_FEASIBILITY_binance_aggtrades.md`).

Scope is **recon only**: prove the source is reachable, parseable, and yields a signed
delta. No caching, no backtest, no lockbox.

## Endpoint (corrected against live probe)

The originally-specified request `{"type":"trades","coin":"BTC"}` to `POST /info` is
**rejected** by the server (`"Failed to deserialize the JSON body into the target
type"`) — live `trades` is a WebSocket subscription, not a `/info` request type.

The working REST request is:

```
POST https://api.hyperliquid.xyz/info
Content-Type: application/json
{"type": "recentTrades", "coin": "BTC"}
```

No API key. Returns a JSON **array** of recent prints (a rolling snapshot of the latest
~N trades — there is no `startTime`/window parameter on this request type).

### Verified response schema

```json
{"coin":"BTC","side":"B","px":"63042.0","sz":"0.00032","time":1783432618019,
 "hash":"0x…","tid":583105994563977,"users":["0x…","0x…"]}
```

- `side`: `"B"` = taker **buy** (aggressor lifted the ask); `"A"` = taker **sell**.
  There are no `"Buy"`/`"Sell"` strings.
- `px`, `sz`: **strings** → cast to `float`.
- `time`: epoch **milliseconds** (UTC).

### Aggressor Delta convention

`signed_size = +sz` when `side == "B"`, `-sz` when `side == "A"`.
`Aggressor Delta = sum(signed_size)`.

## Sample scope (decided)

**Snapshot delta** — one POST, compute the delta over whatever prints the snapshot
returns. Because `recentTrades` has no time window, the script also reports the actual
UTC time span the snapshot covers, so we can see whether it reaches 15 minutes.
(Rejected alternatives: a polling accumulator or a WebSocket loop — both exceed a
recon probe's remit.)

## Structure (four units)

1. `fetch_recent_trades(coin: str = "BTC") -> list[dict]`
   POST the request via stdlib `urllib.request`. If the body is not a JSON list
   (e.g. the deserialize-error string), raise `RuntimeError` carrying the body.
2. `trades_to_frame(trades: list[dict]) -> pd.DataFrame`
   Build a DataFrame; cast `px`/`sz` to float; add `time_utc` (`datetime64[ns, UTC]`)
   from `time`; add `signed_size` from `side`.
3. `aggressor_delta(df: pd.DataFrame) -> float`
   Return `df["signed_size"].sum()`.
4. `main()`
   Fetch → frame → print `df.head()`, the final Aggressor Delta, the trade count, and
   the snapshot's UTC time span. Optional `--coin` arg (default `BTC`).

## Conventions

- stdlib `urllib.request` for HTTP (matches `src/moonface/research/aggtrades_data.py`;
  no new `requests` dependency), plus `pandas`.
- `from __future__ import annotations`, module docstring, full type hints — house style.

## Error handling

- `urllib.error.HTTPError` / `URLError` surface with status/reason.
- Non-list response body → `RuntimeError` with the raw body for legibility.

## Testing

No bundled tests — this is a live-network recon probe and the only pure logic
(`signed_size` / delta sum) is trivial. Verification is a live run of `recon_hl.py`
with its output shown. A fixture-based unit test for the delta math can be added later
if the probe graduates into a kept collector.

## Out of scope (YAGNI)

Polling loop; WebSocket feed; on-disk cache; time-windowed backfill; multi-coin batch;
integration into the tested backtest pipeline.
