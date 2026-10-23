# New-Data Program Readiness - Pre-Registration

Frozen date: 2026-06-17.

## Context

The free-data program is closed. `bab`, `resrev`, `liqrev`, and `calseason`
all failed their frozen gates, and `calseason` closed the final planned
OHLCV-only calendar axis. The production stance remains WAIT on free data.

## Purpose

This cycle decides whether a candidate paid/proprietary dataset is admissible
for a later research program. It does not test alpha.

## Frozen Candidate Data Classes

- `l2_orderbook`: full depth snapshots or high-frequency depth deltas with
  bid/ask price levels and sizes.
- `aggressor_trades`: trade prints with side classification, price, size, and
  exchange timestamp.
- `account_positioning`: long/short account or position ratios with exchange
  timestamp and symbol.

Excluded: OHLCV, funding, basis, open interest, calendar partitions, and any
derived variant of those exhausted free-data axes.

## Readiness Gate

A provider sample passes only if all are true:

- includes one frozen data class;
- covers `BTCUSDT` perpetuals;
- has at least 180 calendar days of history;
- has timestamp coverage of at least 95% against the declared cadence;
- has monotonic timestamps;
- has duplicate timestamp ratio no greater than 1%;
- includes all required fields for the selected data class;
- permits research use, derived-feature retention/use, and sample retention.

## Kill Rule

If no provider sample clears the readiness gate, do not buy, ingest, or
backtest new data. The system remains a WAIT advisor until a different provider
sample is separately registered.

## Promotion Rule

If one provider sample clears the readiness gate, the next cycle may design a
separate alpha preregistration for exactly that data class and provider. Passing
this gate is not evidence of an edge.
