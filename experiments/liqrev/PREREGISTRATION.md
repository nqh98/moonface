# Liqrev Liquidation-Cascade Reversion - Pre-Registration

Frozen date: 2026-06-17.

## Hypothesis

A sharp 4h price move with simultaneous open-interest collapse is forced deleveraging, not informed positioning. The price overshoots and partially reverts over the next 6 bars.

## Data

- 4h USDT perpetual candles from the existing cache/API path.
- Binance Vision futures metrics archive, field `sum_open_interest`.
- Confirmation universe: 16 accepted assets from the volume-ranked candidate queue.
- Discovery exclusions: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- Window: 730 days ending at registration time.

## Event

At bar `i`, compute:

- absolute log return from `close[i-1]` to `close[i]`;
- positive open-interest drop `max(0, -(oi[i] / oi[i-1] - 1))`.

An event fires when both values exceed their trailing 95th percentile over the previous 20 bars. Thresholds use only bars before `i`.

Direction fades the shock:

- negative shock: `LONG`;
- positive shock: `SHORT`.

Events are de-overlapped by the fixed horizon.

## Outcome

Primary outcome is directional simple return from event bar close to close `i+6`, minus 0.001 round-trip cost.

## Gate

The mechanism exists only if all conditions clear:

- net pooled Stouffer Z > 2;
- at least 12 of 16 evaluable assets have positive mean net reversion;
- first time half pooled mean > 0;
- second time half pooled mean > 0;
- leave-one-out pooled mean minimum > 0.

Minimum evaluable set: 8 assets, with at least 10 de-overlapped events per asset.

## Kill Rule

If the net pooled mean is non-positive, forced-deleveraging reversion is absent or cost-eaten on this data. If the pooled mean is positive but the gate or robustness fails, the effect is non-robust. Either result closes `liqrev`; no threshold grid, no horizon grid, no v2.