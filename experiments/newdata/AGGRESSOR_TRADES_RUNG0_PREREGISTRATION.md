# Aggressor Trades Rung-0 Research Cycle - Pre-Registration

Frozen date: 2026-06-17.

Status: frozen design. Do not run this experiment until implementation is
planned and explicitly approved.

## Context

The new-data readiness gate passed for `ExampleVendor` `aggressor_trades` on
2026-06-17. That result is only a data admissibility record. It is not evidence
of a trading edge, signal, return effect, or strategy result.

This preregistration defines the first alpha research cycle that may be run
after implementation approval. The cycle uses only the newly admitted aggressor
trade prints and must not reuse failed free-data families under a new name.

## Hypothesis

On `BTCUSDT` perpetuals, short-horizon net aggressor pressure contains
incremental directional information. Specifically, intervals with unusually
positive signed aggressor volume imbalance should have higher subsequent
returns than intervals with unusually negative signed aggressor volume
imbalance over a fixed short horizon.

The null is that signed aggressor imbalance has no positive out-of-sample
relationship with subsequent returns after chronological validation and
multiple-test discipline.

## Mechanism

Aggressor trades identify which side crossed the spread. Persistent buy
aggression can reveal urgent demand, inventory transfer, stop cascades, or
short-term liquidity taking before those effects are fully visible in coarser
OHLCV bars. Persistent sell aggression is the symmetric case.

This mechanism is microstructure flow-based. It is not a calendar effect,
funding effect, basis effect, open-interest effect, OHLCV pattern, volatility
regime, moving-average effect, or price-only reversal/continuation screen.

## Required Data Fields

Each raw trade print must include:

- `ts_ms`: exchange timestamp in milliseconds.
- `symbol`: instrument identifier; only `BTCUSDT` perpetual records are
  admissible.
- `side`: aggressor side, normalized to `buy` or `sell`.
- `price`: execution price.
- `size`: executed quantity in base or contract units, with the unit documented.

Optional but retained if present:

- `trade_id`: provider or exchange trade identifier for duplicate diagnosis.
- `exchange`: venue identifier if the provider sample combines venues.

No return labels, outcome fields, provider-generated alpha scores, liquidation
feeds, order-book fields, funding fields, basis fields, or open-interest fields
may be used in Rung-0.

## Universe, Timeframe, And Horizon

- Universe: `BTCUSDT` perpetuals only.
- Provider/data class: `ExampleVendor` `aggressor_trades`.
- Minimum sample: the already-readiness-approved 365 calendar days, subject to
  final ingestion audit confirming the same coverage properties.
- Chronology: sort strictly by `ts_ms`; non-monotonic records fail ingestion
  before research begins.
- Aggregation interval: fixed 5-minute buckets.
- Prediction horizon: next 5-minute bucket return, measured from the final trade
  price in bucket `t` to the final trade price in bucket `t+1`.
- Lockbox: final 20% of chronological buckets, sealed before any feature
  inspection, summary statistic review, model selection, or result review.

## Rung-0 Experiment

Rung-0 is a single-feature, single-horizon information test. It is not a
strategy backtest.

For each 5-minute bucket:

1. Compute buy aggressor volume and sell aggressor volume from `side` and
   `size`.
2. Compute signed imbalance:
   `imbalance = (buy_volume - sell_volume) / (buy_volume + sell_volume)`.
3. Drop buckets with zero total aggressor volume.
4. Compute the next-bucket log return from trade prices.
5. On non-lockbox data only, evaluate whether `imbalance[t]` predicts
   `return[t+1]`.

Allowed statistics:

- Spearman information coefficient by chronological fold.
- Newey-West adjusted t-statistic for the pooled non-lockbox relationship.
- Directional monotonicity across five equal-count imbalance buckets, measured
  on non-lockbox out-of-sample folds only.

Disallowed actions:

- No parameter search beyond the fixed 5-minute bucket and 5-minute horizon.
- No strategy backtest, position sizing, stop, take-profit, execution simulator,
  fee rescue, or leverage assumption.
- No sealed lockbox touch before the non-lockbox gate is met and human approval
  is given.
- No alternate horizons, alternate bucket sizes, side remapping, winsorization
  grid, threshold grid, or feature family expansion in this cycle.

## Non-Lockbox Gate

The Rung-0 non-lockbox gate passes only if all are true on chronological
out-of-sample folds drawn entirely before the lockbox:

- At least 6 chronological folds are available after ingestion.
- Median fold Spearman information coefficient is greater than `0.015`.
- At least 4 of 6 folds have positive Spearman information coefficient. If more
  than 6 folds are generated, at least two-thirds must be positive.
- Pooled Newey-West adjusted t-statistic for `imbalance[t] -> return[t+1]` is at
  least `2.0`.
- Five-bucket monotonicity is directionally correct: the highest imbalance
  bucket has a higher mean next-bucket return than the lowest imbalance bucket.
- The effect sign is unchanged after removing the top 1% largest trade-size
  buckets from the non-lockbox folds.

Passing this gate is not a trading result. It only permits a separate request to
open the one-touch lockbox information test.

## Kill Rule

The cycle is killed immediately if any of these occur:

- Ingestion cannot reproduce the readiness requirements: `BTCUSDT` coverage,
  at least 180 days of data, at least 95% timestamp coverage, monotonic
  timestamps, duplicate timestamp ratio no greater than 1%, required fields
  present, and licensed research/derived-feature retention.
- The non-lockbox gate fails any required criterion.
- The implementation requires any unregistered feature, horizon, filter,
  threshold, alternate universe, or free-data field to make the result look
  better.
- Any lockbox bucket is read for feature inspection, summary review, fold
  design, debugging, or result review before an explicit lockbox-opening
  approval.

If the kill rule fires, no Rung-0 variant rescue is allowed. A new attempt
requires a fresh preregistration with a new hypothesis and a new frozen design.

## Lockbox Protection

The final 20% chronological tail is sealed before data inspection. The software
must split raw records by timestamp into development and lockbox partitions
before computing feature summaries. During Rung-0 development:

- CLI defaults must refuse lockbox reads.
- Reports must include `lockbox_touched: false`.
- Any command that opens the lockbox must require an explicit approval flag and
  must be run only after the non-lockbox gate passes.
- The one-touch lockbox result, if later approved, is terminal for this exact
  Rung-0 design.

## New-Data Confirmation

This cycle is genuinely new data because it uses trade-level aggressor side
classification. Prior failed free-data families used OHLCV, funding, basis,
open interest, calendar partitions, or transformations of those fields. The
Rung-0 feature depends on `side` and trade-level `size`, neither of which exists
in the failed free-data families.

Price is used only to calculate the fixed next-bucket return label from the same
trade tape. Price-only features are prohibited in this cycle.

## Approval Gate

This file is frozen. The experiment must not be run, implemented, backtested, or
sealed-tested until a human explicitly approves the implementation plan.
