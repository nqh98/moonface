# carry_measure — RESULTS

Descriptive accounting of a delta-neutral BTC funding-carry position
(long 1x spot / short 1x BTCUSDT USDS-M perp). Nothing here is a
forecast; see experiments/carry_measure/SPEC.md for every convention.

- pipeline commit: `fefc9aea379b2d1b9ea40d748247811a6178b4a6`
- bootstrap seed: 20260716
- input `funding`: `.claude/worktrees/carry-measure/cache/matrix/funding_BTC_USDT_USDT.csv` sha256 `1d60c285220085e3f10fa5dabad4d4a476a7bffcccd7a5861baf7190d416ba03`
- input `perp`: `.claude/worktrees/carry-measure/.backtest_cache/BTC_USDT:USDT_1h.csv` sha256 `48115107950bcf3efd864bbb3c1dd751d3ea97317524805d8fae17a8f86cf366`
- input `spot`: `.claude/worktrees/carry-measure/.backtest_cache/BTC_USDT_1h.csv` sha256 `ca8f20222017a0fb8f2314c0a94c4c59bb61369c1dda2cea89924b555d4b859f`
- window: 2020-01-01 00:00 -> 2026-06-30 16:00 UTC (6.50 years)
- margin buffer: 30% of notional; total capital = notional x 1.30
- cost convention: quoted round-trip bps = one leg's in+out; a single trade
  on one leg costs half the quoted bps; entry, exit and resizes trade both
  legs (full position in-and-out therefore costs 2x the quoted bps).
- funding is received at every 8h timestamp incl. the first; mark proxy =
  open of the 1h bar at the funding timestamp.

## Data provenance notes

- Binance BTC/USDT spot 1h history is missing 31 hours across 14 gaps in this window (a real exchange-side gap, confirmed via two independent ccxt calls). Each missing hour was spliced in from the corresponding Coinbase BTC/USD candle (ccxt 'coinbaseexchange'), never interpolated. Substituted hours (UTC): 2020-02-19 12:00, 2020-02-19 13:00, 2020-02-19 14:00, 2020-02-19 15:00, 2020-02-19 16:00, 2020-03-04 10:00, 2020-04-25 02:00, 2020-04-25 03:00, 2020-06-28 02:00, 2020-06-28 03:00, 2020-06-28 04:00, 2020-11-30 06:00, 2020-12-21 14:00, 2020-12-21 15:00, 2020-12-21 16:00, 2020-12-21 17:00, 2020-12-25 02:00, 2021-02-11 04:00, 2021-03-06 02:00, 2021-04-20 02:00, 2021-04-20 03:00, 2021-04-25 05:00, 2021-04-25 06:00, 2021-04-25 07:00, 2021-08-13 02:00, 2021-08-13 03:00, 2021-08-13 04:00, 2021-08-13 05:00, 2021-09-29 07:00, 2021-09-29 08:00, 2023-03-24 13:00. This affects Q5 (descriptive basis) only -- funding accounting (Q1-Q4, Q6-Q7) runs on the perp series alone.

## Q1 — gross carry (rate space, % of held notional)

| year | intervals | annualized gross % | monthly mean % | monthly std % |
|---|---|---|---|---|
| 2020 | 1098 | 17.19 | 1.437 | 1.338 |
| 2021 | 1095 | 30.61 | 2.551 | 2.284 |
| 2022 | 1095 | 4.16 | 0.347 | 0.216 |
| 2023 | 1095 | 7.87 | 0.655 | 0.395 |
| 2024 | 1098 | 11.92 | 0.996 | 0.783 |
| 2025 | 1095 | 5.13 | 0.427 | 0.183 |
| 2026 | 543 | 1.13 | 0.093 | 0.243 |

Monthly gross carry, % of notional:

```
   -0.532 ..     0.116 | ####### 8
    0.116 ..     0.764 | ######################################## 43
    0.764 ..     1.412 | ########### 12
    1.412 ..     2.060 | ##### 5
    2.060 ..     2.708 | #### 4
    2.708 ..     3.356 | ## 2
    3.356 ..     4.004 |  0
    4.004 ..     4.652 | ## 2
    4.652 ..     5.300 |  0
    5.300 ..     5.948 | # 1
    5.948 ..     6.596 |  0
    6.596 ..     7.244 | # 1
```

## Q2 — net carry grid (annualized %, after costs)

| convention | cost (bps rt) | ann. net % of notional | ann. net % of capital |
|---|---|---|---|
| R0 | 5 | 75.61 | 58.16 |
| R0 | 10 | 75.54 | 58.11 |
| R0 | 20 | 75.40 | 58.00 |
| R1a | 5 | 13.44 | 10.34 |
| R1a | 10 | 13.34 | 10.26 |
| R1a | 20 | 13.14 | 10.11 |
| R1b | 5 | 11.89 | 9.15 |
| R1b | 10 | 11.71 | 9.01 |
| R1b | 20 | 11.36 | 8.74 |

## Q3 — negative-funding episodes

- episodes: 482; longest run: 24 consecutive 8h intervals; median duration 1.0, p90 4.0 intervals

| deepest episodes | start (UTC) | end (UTC) | intervals | depth % of notional |
|---|---|---|---|---|
| #1 | 2020-03-12 16:00 | 2020-03-20 08:00 | 24 | -1.037 |
| #2 | 2020-03-28 00:00 | 2020-04-02 00:00 | 16 | -0.407 |
| #3 | 2022-11-09 16:00 | 2022-11-11 16:00 | 7 | -0.320 |
| #4 | 2021-07-19 16:00 | 2021-07-22 00:00 | 8 | -0.159 |
| #5 | 2021-07-23 08:00 | 2021-07-26 00:00 | 9 | -0.157 |

## Q4 — drawdown of the cumulative net curve (10 bps cell)

| convention | max DD % of notional | DD 90% CI (bootstrap) | peak | trough | longest underwater (days) | DD / avg annual carry |
|---|---|---|---|---|---|---|
| R0 | 4.255 | [1.060, 3.579] | 2026-02-05 08:00 | 2026-05-09 08:00 | 137 | 0.06x |
| R1a | 1.100 | [0.305, 1.007] | 2020-03-12 08:00 | 2020-04-23 08:00 | 149 | 0.08x |
| R1b | 1.666 | [0.341, 1.649] | 2020-03-12 08:00 | 2020-04-23 08:00 | 149 | 0.14x |

## Q5 — spot-perp basis at position boundaries (descriptive)

Full-window hourly basis percentiles, bps:

| p1 | p5 | p25 | p50 | p75 | p95 | p99 |
|---|---|---|---|---|---|---|
| -8.4 | -6.4 | -4.9 | -3.7 | 1.2 | 10.5 | 16.9 |

| year | p5 bps | p50 bps | p95 bps |
|---|---|---|---|
| 2020 | -7.6 | 0.5 | 12.6 |
| 2021 | -6.4 | 4.7 | 16.9 |
| 2022 | -6.9 | -4.4 | -1.2 |
| 2023 | -5.9 | -3.8 | 6.7 |
| 2024 | -5.8 | -2.8 | 8.8 |
| 2025 | -5.9 | -4.4 | -2.4 |
| 2026 | -6.4 | -4.9 | -3.4 |

- entry haircut (sell perp/buy spot): median 3.7 bps, 5th-pct-adverse 6.4 bps
- exit haircut (buy perp/sell spot): median 0.0 bps, 95th-pct-adverse 10.5 bps
- haircuts are not folded into Q2; they are boundary costs to read next to it.

## Q6 — year-by-year gross carry: is this shrinking?

| year | intervals | annualized gross % |
|---|---|---|
| 2020 | 1098 | 17.19 |
| 2021 | 1095 | 30.61 |
| 2022 | 1095 | 4.16 |
| 2023 | 1095 | 7.87 |
| 2024 | 1098 | 11.92 |
| 2025 | 1095 | 5.13 |
| 2026 | 543 | 1.13 |

No trend is fitted and nothing is extrapolated; the table is the answer.

## Q7 — worst month and worst quarter (10 bps cell)

Plain-dollar figures are on $100,000 of total capital
(notional $76,923 + margin buffer).

| convention | worst month | net % | net $ | worst quarter | net % | net $ |
|---|---|---|---|---|---|---|
| R0 | 2026-04 | -1.910 | -1,469 | 2026-Q2 | 1.517 | +1,167 |
| R1a | 2026-04 | -0.203 | -156 | 2026-Q2 | 0.107 | +82 |
| R1b | 2020-03 | -0.701 | -539 | 2026-Q2 | 0.094 | +72 |

## Risks (read before acting on any number above)

1. **Exchange/counterparty tail risk.** Both legs sit on one venue. An
   exchange failure is a total-position event that no table above prices.
   This risk is stated, not quantified — historical funding data contains
   no information about it.
2. **Liquidation risk on the short perp leg.** With a 30% USDT
   buffer and no top-ups, the short leg is exhausted by a rally of about
   30% before maintenance margin. In this window the largest
   price run-up was 2523.7% (2020-03-13 00:00 -> 2025-10-06 16:00).
   Largest run-up inside a trailing window (how fast top-ups must arrive):

   | window (days) | max run-up % |
   |---|---|
   | 7 | 39.3 |
   | 14 | 66.9 |
   | 30 | 129.5 |
   | 60 | 169.5 |
   | 90 | 263.0 |

   The spot leg gains what the perp leg loses, but spot gains are not
   automatically usable as perp margin unless collateral is arranged that
   way; sloppy margin management converts a hedged position into a
   liquidation.
3. **Stablecoin/collateral risk.** The margin buffer and funding receipts
   are USDT-denominated; a USDT break is a correlated loss on the buffer
   and the carry stream.
4. **Spot custody/borrow assumptions.** The accounting assumes spot is
   bought with own capital and held on-venue; no borrow cost and no
   custody yield. Off-venue custody reduces counterparty exposure but
   slows margin top-ups (see risk 2).
5. **Decay.** The Q6 table is the record; the past level of carry is not
   a promise about its future level.

## Plain-language summary

Over 6.5 years a delta-neutral BTC carry position earned a
gross funding stream that, at the middle cost assumption (R0, 10 bps),
nets to about 75.5% per year on notional
(58.1% on total capital including the margin
buffer). Across all stated conventions and cost levels the annualized
net range was 8.7% to
58.2% on capital. The funding stream was
negative in 482 distinct episodes (longest
24 consecutive 8h intervals), the
worst month and quarter are in Q7, and the deepest drawdown of the net
curve was 4.25% of notional with
137 days as the longest stretch under a
prior high. The year-by-year table (Q6) shows whether the carry level is
shrinking; it is reported without extrapolation.

This is input to a personal investment decision, not a research verdict.
