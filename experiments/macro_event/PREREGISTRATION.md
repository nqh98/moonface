# Preregistration — Macro event-window study (FOMC/CPI event time, BTC)

Date frozen: 2026-07-03. Approved as the one new research cycle of the
2026-07-03 research-director review (candidate 2b), alongside the Deribit
forward collector (2a) and the queued ETF-flow readiness pass (2c).

## Hypothesis (frozen before any data contact)

BTC earns a positive uncertainty-resolution premium in fixed 24h windows
anchored to scheduled US macro releases — FOMC statements (14:00 ET) and
CPI prints (08:30 ET) — over 2022-01..2026-06, the period in which BTC has
carried a persistent macro beta. Mechanism: mandated de-risking into
scheduled uncertainty (the equity pre-FOMC drift of Lucca-Moench, 2015)
transmitted to BTC; the identified loser pays for uncertainty reduction by
mandate, not by mistake.

## Why this is not a disguised retest

- The conditioning variable is an EXTERNAL event calendar — not derivable
  from price, funding, basis, OI, taker flow, breadth, or any tested feed
  (Q6-clean). The closed `calseason` family tested fixed CALENDAR cells
  (weekday/weekend, funding settlement), which repeat whether or not
  information arrives; event windows are anchored to information arrival.
  Neither family's cells are a transform of the other's.
- Exposure is episodic (~89 events x 24-48h over 4.5y, <6% time-in-market),
  the one structure the program's replicated drawdown-wall finding does not
  tax. This study therefore does not re-fight the wall.

## Frozen design

- Instrument: BTCUSDT perp, 1h candles (Binance fapi, house fetcher).
- Events: 36 FOMC statement datetimes + 53 CPI release datetimes,
  2022-01-01..registration date, timestamps DST-correct via
  America/New_York. Calendar sources, verified 2026-07-03:
  federalreserve.gov/monetarypolicy/fomccalendars.htm (Sep-2023 meeting
  independently confirmed); BLS archive filenames
  (news.release/archives/cpi_MMDDYYYY.htm) spot-verified for 2022-2024;
  published BLS schedules for 2025-2026. October-2025 CPI data month was
  never published (government shutdown): 2025 has 11 releases.
- Cells (all four, no additions): {fomc, cpi} x {pre24h, post24h}.
  pre24h = [t0-24h, t0), post24h = [t0, t0+24h).
- Direction: LONG in every cell (risk-premium sign), frozen here.
- Execution semantics: close-to-close on completed 1h bars only; a close
  more than two intervals stale is missing data and drops the event.
- Cost: COST_FRACTION = 0.001 of notional per event (one round trip),
  the house number. All gates are NET of cost (bookdepth lesson).
- Gate per cell (conjunctive): n >= 20; net pooled mean > 0; one-sided
  percentile bootstrap p(mean <= 0) < 0.0125 (= 0.05/4 Bonferroni,
  breadth-v2 precedent; 10,000 resamples, seed 20260703); both
  chronological halves have positive net mean.
- Verdict: any cell clears => `forward_candidate` (next step is a
  human-gated forward paper registration — NOT promotion, NOT sizing).
  No cell clears => `closed_negative`.

## Kill rule

No cell clears the frozen gate => the macro event-window family is CLOSED.
No window-length drift, no event-set drift (no NFP/PCE rescue), no
direction flip, no vol-normalized re-scoring. A `forward_candidate` that
later fails its forward registration closes the family the same way.

## Power caveat (stated up front)

n = 36 (FOMC) / 53 (CPI) per window. This is a breadth_thrust-class power
situation: the gate can only detect large effects, and a clean negative
here means "no large effect", not "no effect". That bound is accepted; the
family will not be reopened to chase smaller effects with more cells.
