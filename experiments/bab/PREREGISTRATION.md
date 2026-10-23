# BAB v1 — Betting-Against-Beta / low-volatility cross-sectional long-short

Pre-registered **before any universe data was seen**. Frozen design; a changed
design requires a new experiment directory (the `register` command refuses to
overwrite). This is the next-cycle program approved 2026-06-17, the cheapest
credible test of the one escape hatch the program left open: a *market-neutral,
second-moment* cross-sectional sort, structurally exempt from the single-asset
drawdown wall.

## 1. Hypothesis

A market-neutral portfolio that is **long the low-beta quintile and short the
high-beta quintile** of liquid USDT perps, weighted so the book is ex-ante
beta-neutral, earns positive out-of-sample risk-adjusted return. Equivalently:
high-beta crypto perps are systematically *overpriced* relative to their risk.

## 2. Mechanism

Leverage-constrained and lottery-seeking participants — dominant in retail
crypto — overpay for high-volatility, high-beta names because they offer cheap
embedded leverage and lottery-like upside, while constrained arbitrageurs
cannot fully short them. The resulting flat-to-inverted risk-return slope is the
betting-against-beta / low-volatility anomaly (Frazzini & Pedersen 2014), the
most replicated anomaly outside crypto. It is a **second-moment** sort, signed
and economically independent of the momentum/carry first-moment sorts already
rejected in `experiments/xsection/` (mom_30 DSR 0.83, closed negative).

## 3. Required inputs

OHLCV multi-asset universe only: Binance Vision survivorship-clean daily klines
(symbol discovery + quote volume) plus funding rates for accrual accounting. No
order-book, OI, or metrics-archive inputs. Beta is estimated against an
equal-weight index built from the same universe klines.

## 4. Construction (single, no grid)

- **Universe:** top-20 USDT perps by mean trailing-30d quote volume, listed
  ≥ 365 days, rebuilt monthly (`build_universe`, reused unchanged from xsection).
- **Index:** equal-weight daily return of the active month's universe members.
- **Signal:** each member's OLS beta of daily returns on the index over the
  **trailing 60 days** (≥ 20 overlapping days required, else excluded).
- **Book:** weekly rebalance; long bottom beta quintile, short top beta quintile
  (k = 4 names per leg), each leg scaled by 1 / (mean leg beta) so ex-ante
  portfolio beta ≈ 0 (Frazzini-Pedersen weighting); equal-weight neutral
  fallback if a leg's mean beta is non-positive.
- **Costs:** 5 bps taker per side of traded notional on turnover, plus actual
  per-symbol funding accrual (longs pay positive funding, shorts receive).
- **Window:** 3 years ending at registration; final 20% sealed as a one-touch
  lockbox tail. Exactly **one** construction (`bab_60`); n_trials = 1.

## 5. Success criteria (frozen gate ladder)

The program's standard ladder, identical thresholds to xsection:

1. **Screen** — positive mean daily return over the first 70% of the research
   (pre-fence) window, ≥ 60 screen days.
2. **Holdout** — holdout MAR > 0 and holdout drawdown ≥ −0.30.
3. **DSR** — lineage-deflated Deflated Sharpe ≥ **0.95**.
4. **Lockbox tail** — one-touch tail MAR ≥ 1.0, drawdown ≥ −0.30, ≥ 30 days.

Promotion requires clearing **every** stage. A near-miss is a reject (the
mom_30 precedent: DSR 0.83 with a −91.6% sealed tail).

## 6. Failure interpretation

If `bab_60` fails any stage, the betting-against-beta / leverage-constraint
premium **does not survive in liquid crypto perps net of costs**. Combined with
the already-dead momentum/carry sort, that falsifies *both* signed first- and
second-moment cross-sectional risk premia on this universe — a strong negative
that collapses most of the remaining market-neutral hypothesis space and pushes
the honest program output back to the WAIT advisor plus a new-data requirement
(`docs/findings/PROGRAM_CONCLUSION.md`).

**Kill rule:** closed_negative ⇒ the low-volatility/BAB family is terminal on
this universe; no parameter rescue, no lookback grid, no v2.
