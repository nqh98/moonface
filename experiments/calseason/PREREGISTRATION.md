# Calseason Calendar Seasonality - Pre-Registration

Frozen date: 2026-06-17.

## Hypothesis

Expected 4h returns differ by fixed clock position around 8h funding-settlement boundaries and by weekend/weekday regime. This is not a price signal; it is a fixed calendar partition.

## Data

- 4h USDT perpetual OHLCV only.
- Confirmation universe: 16 accepted assets from the volume-ranked candidate queue.
- Discovery exclusions: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`.
- Window: 730 days ending at registration time.

## Return Unit

For bar `i`, return is `close[i] / close[i-1] - 1`, assigned by bar `i` open timestamp in UTC.

## Fixed Cells

- `funding_pre`: UTC hour in `{4, 12, 20}`.
- `funding_post`: UTC hour in `{0, 8, 16}`.
- `weekend`: UTC weekday Saturday/Sunday.
- `weekday`: UTC weekday Monday-Friday.

These four cells are the complete test set. No alternate hours, sessions, months, holidays, or threshold variants are admissible in this cycle.

## Gate

A cell clears only if all are true:

- `abs(Stouffer Z) > 3`;
- at least 12 of 16 evaluable assets have mean return with the same sign as the pooled cell;
- first time half pooled mean has the same sign as the full pooled cell;
- second time half pooled mean has the same sign as the full pooled cell.

Minimum evaluable set: 8 assets with at least 30 returns in the cell.

## Kill Rule

If no cell clears, there is no exploitable bar-level calendar structure on free OHLCV. This closes the last planned non-price/non-positioning free-data axis; the honest output becomes the WAIT advisor plus a genuinely new-data requirement. No cell expansion, no alternate partition, no v2.
