# Free-Data Feasibility: Deribit Options Chain (per-strike OI + IV)

Date: 2026-07-02. Scope: Stage 0 of the H1 dealer-gamma lane — data
acquisition feasibility ONLY. No signal design beyond what the approved plan
sketched, no data analysis, no alpha work. Mirrors the structure of
`FREE_DATA_FEASIBILITY_binance_aggtrades.md`.

## Requirement

The dealer-gamma regime hypothesis needs, per day (or finer), the full BTC
option chain: per-strike/per-expiry **open interest** and **implied
volatility** plus the underlying price — enough to compute net dealer gamma
and its flip point. The `newdata` readiness gate requires >= 180 days of
history, coverage >= 0.95, monotonic timestamps, <= 1% duplicates, and a
license permitting research, derived features, and retention. The program
mandate restricts sources to free/public data.

## Findings

**Q1. Does a free source of the CURRENT chain exist?** YES. Deribit public
API `public/get_book_summary_by_currency?currency=BTC&kind=option` — keyless,
one call returns the whole chain (922 instruments on 2026-07-02) with
`open_interest`, `mark_iv`, `underlying_price`, strike/expiry/type parseable
from `instrument_name`. Verified live today.

**Q2. Does a free source of >= 180 days of HISTORICAL per-strike OI+IV
exist?** NO.
- Deribit public API: no historical endpoint for per-strike OI or IV
  (historical trades are paginatable and carry per-trade IV, but OI cannot be
  soundly reconstructed from trades — no open/close flags).
- Tardis.dev/Deribit partnership free tier: full granularity but only the
  FIRST day of each month without a paid key — ~3% coverage vs the 0.95 gate.
- CryptoDataDownload: Deribit options files are OHLCV-only (no OI, no IV) and
  behind a paid Plus+ subscription.
- Amberdata, Laevitas: paid.
- No community bulk archive (GitHub/Kaggle) with per-strike OI+IV coverage
  was found.

**Q3. Is DVOL a substitute?** NO. The already-gated `implied_vol` class
(Deribit DVOL index, `exogenous/deribit_dvol.py`) is a single aggregate IV
index; dealer gamma needs the per-strike surface and OI.

**Q4. License.** Deribit public API market data is served keyless for
research use; the same license stance was accepted for DVOL in the existing
`implied_vol` registration. No new license obstacle for forward collection.

**Q5. Would a forward collector satisfy the gate?** YES, mechanically: one
daily snapshot call appended to a CSV manifest reaches 180 days of history
around 2027-01, with coverage/monotonicity under our control. It would also
require adding an `options_chain` data class (fields `ts_ms, symbol,
expiry_ms, strike, option_type, oi, iv, underlying_price`) to the frozen
`newdata` schema — an amendment commit, per the approved plan.

## Conclusion — BLOCKED at Stage 0, human decision required

No free historical source satisfies the readiness gate today. The two honest
options (per the approved plan; choosing is human-gated):

- **(A) Forward-collect**: ship a small daily snapshot collector now (mirrors
  `deribit_dvol.py`), register the provider once >= 180 days accumulate
  (~2027-01), then freeze the alpha prereg. Cost: one API call/day; the lane
  sleeps until the gate is reachable.
- **(B) Close the lane** at Stage 0 as data-infeasible under the free-data
  mandate.

No alpha preregistration is frozen until the readiness gate passes; the
dealer-sign convention ambiguity must be resolved at that future prereg time,
not after seeing results.

Sources: [Deribit API](https://docs.deribit.com/), live probe of
`get_book_summary_by_currency` (2026-07-02);
[Tardis.dev Deribit docs](https://docs.tardis.dev/historical-data-details/deribit);
[Deribit/Tardis partnership](https://insights.deribit.com/exchange-updates/celebrating-our-tardis-dev-partnership-get-free-historical-data/);
[CryptoDataDownload Deribit](https://www.cryptodatadownload.com/data/deribit/).
