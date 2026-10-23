# Liqladder Liquidation-Ladder Magnet - Pre-Registration

Frozen date: 2026-07-02.

## Hypothesis

Pending liquidation levels are ex-ante computable from open-interest increments
(entry-price clusters) split across conventional leverage tiers. When the
estimated pending-liquidation notional just below spot vastly exceeds that just
above (or vice versa), price CONTINUES toward the heavy shelf over the next 6
bars: liquidation is price-insensitive forced flow and the participants
positioned to fade the approach are the ones being liquidated. This is the
inverse orientation of the closed `liqrev` lane, which tested reversion after
the collapse; this lane tests continuation into it. The two verdicts are
independent: liqrev's positive-but-null aftermath reversion says nothing about
the approach.

## Data

- 1h USDT perpetual candles from the existing cache/API path.
- Binance Vision futures metrics archive, fields `sum_open_interest` and
  `count_long_short_ratio` (5-min snapshots, as-of joined to 1h bars).
- Confirmation universe: 16 accepted assets from the volume-ranked candidate
  queue (same frozen procedure as liqrev).
- Discovery exclusions: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- Window: 730 days ending at registration time.

Declared feasibility deviation from the drafted design: the ladder updates at
1h bar resolution (aligned OI deltas at bar close), not raw 5-min ticks —
5-min price data is not cached for the universe and the mechanism does not
require sub-hour entry-price precision at 0.25% bin width.

## Ladder

Multiplicative price bins of width 1.0025 (0.25%). Per 1h bar, in order:

1. **Consume**: bins traversed by the bar's low..high range are zeroed (their
   stops fired).
2. **Update**: if OI rose by dOI at close p, add dOI/4 per leverage tier
   L in {10, 25, 50, 100}, split long/short by fl = ratio/(1+ratio) from the
   long/short account ratio (0.5 if unavailable), at estimated liquidation
   levels p*(1 - 1/L + 0.005) (long side, below) and p*(1 + 1/L - 0.005)
   (short side, above). If OI fell, the whole ladder decays by the OI ratio
   (voluntary closes); OI hitting zero clears it.

All state uses information at or before the signal bar close.

## Event

At bar i (after warmup of 14 bars), over ladder bins within +/-5% of spot:

- asymmetry `A = (D_down - D_up) / (D_down + D_up)` where D_side is total
  ladder mass on that side of spot.

An event fires when |A| > 0.6 AND the nearest same-side bin whose mass is in
the top decile of window bin masses sits within 1 x ATR(14) of spot.

Direction is CONTINUATION toward the heavy side: down-heavy -> `SHORT`,
up-heavy -> `LONG`. Events are de-overlapped by the fixed horizon.

## Outcome

Primary outcome is directional simple return from event bar close to close
`i+6`, minus 0.001 round-trip cost.

## Gate (Stage A - mechanism)

The mechanism exists only if all conditions clear:

- net pooled Stouffer Z > 2;
- at least 12 of 16 evaluable assets have positive mean net continuation;
- first time half pooled mean > 0;
- second time half pooled mean > 0;
- leave-one-out pooled mean minimum > 0.

Minimum evaluable set: 8 assets, with at least 10 de-overlapped events per
asset.

## Stage B (frozen now, built and run only if Stage A passes)

BTCUSDT 1h, same frozen trigger, 60/20/20 chronological split with the sealed
tail opened only after the validate slice passes; economics judged by the
locked program bar (`ECON_BAR`: PF >= 1.2, expectancy >= 0.05R, MAR >= 0.5,
MaxDD <= 30R at f=0.01, robust_frac >= 0.60) via `evaluate_econ`; exits fixed
bracket at 2R target / 1R stop on ATR(14) risk units. No exit grid, no
parameter search.

## Kill Rule

If the net pooled mean is non-positive, ladder-magnet continuation is absent
or cost-eaten on this data. If the pooled mean is positive but the gate or
robustness fails, the effect is non-robust. Either result closes `liqladder`;
no threshold grid, no horizon grid, no alternative tier weights, no v2.
Stage B failing any gate closes the lane with no retuning.
