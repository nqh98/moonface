# resrev v1 — cross-sectional short-term residual reversal (stat-arb)

Pre-registered **before any universe data was seen**. Frozen design; a changed
design requires a new experiment directory (`register` refuses to overwrite).
This is reopening cycle 4 (`experiments/BACKLOG.md` item 4), the highest
information-gain market-neutral mechanism left: a *mean-reversion* book on the
idiosyncratic residual, distinct from the dead momentum/carry first-moment sorts
and from the dead BAB second-moment sort.

## 1. Hypothesis

After removing market (index-beta) return, a perp's **idiosyncratic residual
return mean-reverts over one bar**: a market-neutral book **long the bottom
residual decile** (recent idiosyncratic losers) and **short the top residual
decile** (recent idiosyncratic winners), beta-neutralised, earns positive
out-of-sample expectancy net of costs.

## 2. Mechanism

Liquidity-demand shocks — single-name unwinds, liquidation wicks — push a perp
off its peer-implied fair value. Liquidity providers who absorb that flow are
compensated by the subsequent reversion. This is the *inverse* of momentum
(continuation of informed flow) at a shorter horizon on the *residual*, not the
raw return — the short-term reversal anomaly (Lehmann 1990, Lo–MacKinlay 1990)
in its market-neutralised, residual form.

## 3. Required inputs

OHLCV multi-asset universe only: Binance Vision survivorship-clean klines
(symbol discovery + quote volume) plus funding for accrual. Beta and the index
are built from the same universe klines. No order-book / OI / metrics inputs.

## 4. Construction (single, no grid)

- **Universe:** top-20 USDT perps by mean trailing-30d quote volume, listed
  ≥ 365 days, rebuilt monthly (`build_universe`, reused unchanged).
- **Index:** equal-weight daily return of the active month's universe members.
- **Beta:** OLS of each member's daily returns on the index over the trailing
  **60 days** (≥ 20 overlapping days), reused from `bab` unchanged.
- **Signal:** residual at decision day t, `resid_t = ret_t − β_t · index_t`.
- **Book:** **daily** rebalance; long bottom residual decile, short top decile
  (k = 2 names per leg at top-20), each leg scaled by 1 / (mean leg beta) so the
  book is ex-ante beta-neutral; equal-weight neutral fallback for a non-positive
  mean leg beta; one-day hold.
- **Costs:** 5 bps taker per side of traded notional on turnover (full turnover
  every bar — the cost crux), plus actual per-symbol funding accrual.
- **Window:** 3 years ending at registration; final 20% sealed lockbox tail.
  Exactly **one** construction (`resrev_1`); n_trials = 1.

### Feasibility deviation from the backlog (declared before freezing)

The backlog item specified 4h bars. The survivorship-clean universe is only
ingested at **daily** frequency (`universe_data` fetches 1d klines for every
archived symbol, including delisted ones); a 4h backfill of 700+ symbols is not
feasible in this harness without paginated rate-limited fetches and would lose
the survivorship-clean property. Daily one-day residual reversal is the original,
equally-documented form of the anomaly, so the test runs daily. This is a
feasibility choice made with no data seen, mirroring how OI was once shelved on
feasibility — not a result-driven design change.

## 5. Success criteria (frozen gate ladder)

A **cost-first pre-screen runs first** (the book-depth lesson: a gross effect
that is 10× under cost is not tradeable):

0. **Cost-first** — net-of-cost mean daily return over the research (pre-fence)
   window > 0, with its Stouffer-style Z reported. If net mean ≤ 0 the strategy
   is cost-dead and the verdict is closed_negative immediately; the ladder does
   not run.

Then the program's standard ladder on the net series, identical thresholds:

1. **Screen** — positive mean daily return over the first 70% of the research
   window, ≥ 60 screen days.
2. **Holdout** — holdout MAR > 0 and holdout drawdown ≥ −0.30.
3. **DSR** — lineage-deflated Deflated Sharpe ≥ **0.95**.
4. **Lockbox tail** — one-touch tail MAR ≥ 1.0, drawdown ≥ −0.30, ≥ 30 days.

Promotion requires clearing every stage. A near-miss is a reject.

## 6. Failure interpretation

Two distinguishable failures, both informative:

- **Gross effect absent** (net mean ≤ 0 *and* gross mean ≤ 0) ⇒ idiosyncratic
  one-day reversion does not exist on this universe; the liquidity-provision
  premium is zero here.
- **Gross present, net ≤ 0** ⇒ the premium exists but is entirely consumed by
  perp trading costs at the only frequency it lives at — the book-depth verdict
  class, confirming free-data microstructure premia are uniformly sub-cost in
  this harness.

Either result closes the cross-sectional mean-reversion space.

**Kill rule:** closed_negative ⇒ residual reversal is terminal on this universe;
no horizon grid, no lookback grid, no v2.
