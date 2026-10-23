# liqprem — PREREGISTRATION (frozen)

Source: `docs/research-log/specs/2026-07-06-freedata-addendum-design.md` §H2.
Free-data addendum hypothesis 3 of 3 (`advval` KILL 2026-07-06, `eventtime`
KILL 2026-07-06). Signal discovery only. No trading, no promotion.

## Hypothesis

Illiquid USDT perps out-return liquid ones — compensation for exit-cost risk
(Amihud 2002). This is the standing *level* premium for liquidity provision,
distinct from the dead momentum/carry (first moment), BAB (second moment) and
residual reversal (short-horizon liquidity *demand*) families.

## Frozen construction (n_trials = 1)

| Parameter | Value |
|---|---|
| Signal | Amihud illiquidity = trailing-30d mean of \|daily return\| / daily dollar volume |
| Universe | minimum-viability floor: listed >= 365d AND trailing-30d **median** daily dollar volume >= $1,000,000 (NOT top-N by volume — that truncates the illiquid tail) |
| Book | long most-illiquid quintile, short most-liquid quintile, each leg beta-neutral scaled (60d OLS beta vs the equal-weight universe index) |
| Rebalance | every 7 days, equal weight within leg |
| Costs | **punitive asymmetric**: 25 bps/side illiquid (long) leg, 5 bps/side liquid (short) leg, charged on turnover |
| Funding | actual per-symbol daily funding accrual; longs pay positive funding |
| Window | 3.0 years back from registration timestamp; final 20% is the one-touch lockbox tail |

Two construction choices are load-bearing and are recorded here so they are
not mistaken for arbitrary tuning:

- **Median, not mean, dollar volume** for the viability floor. A single
  listing-pump print would otherwise buy admission for a symbol that is
  untradeable on every other day of the window.
- **Leg size k derived from the scored count, not a fixed top-N.** The
  viability universe varies in size month to month; a fixed k would silently
  redefine what "quintile" means as the universe grows.

## Gates, in order

1. **Cost-first pre-screen** — net-of-punitive-cost Stouffer Z > 0 over the
   research window. Fails ⇒ the ladder never runs.
2. Standard `gate_construction` ladder: stage 1 screen mean > 0 with >= 60
   days, stage 2 holdout MAR > 0 with drawdown >= -0.30, stage 3 deflated
   Sharpe >= 0.95, stage 4 one-touch lockbox tail.

## Permanent kill rules

- **`no_premium`** — gross Stouffer Z <= 0 ⇒ no liquidity premium exists in
  this cross-section.
- **`unharvestable`** — gross present but net Z <= 0 under the frozen punitive
  costs ⇒ book-depth verdict class (real but unharvestable).

Either outcome closes the **entire cross-sectional space permanently**. As the
last of the three-hypothesis free-data budget, a negative here also means free
data is unconditionally, permanently finished; the program's only forward paths
become the frozen paper threads and the maturing new-data collectors (Deribit
options readiness ~2027-01).

## Data fingerprints

Recorded into `verdict.json` at run time: `universe_symbols` (symbols with any
data in window), `viability_members` (union of monthly viability universes),
`funding_symbols`, and the frozen `start_ms` / `end_ms` / `fence_ts` from
`registration.json`.

## Run discipline

`register` before `run`; `registration.json` refuses overwrite; `verdict.json`
refuses re-run. One cycle, one verdict, written once. The real-data run is a
per-cycle human go.

```
.venv/bin/python tools/liqprem.py register
.venv/bin/python tools/liqprem.py run --cache-dir .backtest_cache
```

Implementation: `src/moonface/research/liqprem.py`, `tools/liqprem.py`.
Plan: `docs/research-log/plans/2026-07-28-liqprem.md`.
