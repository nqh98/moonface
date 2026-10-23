# SPEC — `carry_measure`: Delta-Neutral Funding Carry (Measurement Lane)

Status: DRAFT — awaiting human review before any implementation.
Source brief: handoff "LANE BRIEF — carry_measure" (2026-07-16).
Design approved section-by-section in the brainstorming session of 2026-07-16.

## 0. Classification (hard, unchanged from brief)

- This is a **measurement lane**: descriptive accounting over historical
  contractual cash flows. Nothing is predicted.
- NOT a strategy, signal, or research hypothesis. NO registration, NO
  identity_hash freeze, NO EDGE FOUND / KILL verdict, NO entry/exit
  optimization.
- Forbidden scope creep (each voids the classification → stop-and-ask):
  - any predictive entry/exit condition ("hold carry only when …");
  - any parameter sweep whose objective is return maximization;
  - any output phrased as a recommendation.
- Conditional/threshold variants only as **descriptive stratification**
  (reporting, not selection).
- Anything worth computing that is not in Q1–Q7 after results are seen goes
  to `experiments/carry_measure/AMENDMENTS.md`, never into the frozen run.

## 1. Position being measured

Long 1 BTC spot + short 1 BTC-equivalent of the BTCUSDT USDⓈ-M perpetual,
collecting funding on the short leg.

Because the perp is coin-quantity based, a 1-BTC-vs-1-BTC hedge is
**delta-neutral by construction**: price moves never open a delta gap. What
drifts is (a) the USD notional both legs share, and (b) the margin on the
short leg (bleeds in rallies, needs top-ups). "Rebalancing" is therefore
modeled as notional-management conventions, not delta repair:

| Convention | Definition | Rebalance trades |
|---|---|---|
| **R0** | BTC-units hedge, entered once, never resized | none |
| **R1a** | constant-USD-notional, both legs resized on the first funding timestamp of each calendar month | monthly |
| **R1b** | constant-USD-notional, both legs resized when notional drifts >10% from target | event-driven |

The R1 target notional is the USD notional at entry (first funding
timestamp of the window). The position is entered once at window start and
exited once at window end; entry/exit costs are charged there.

R1 cadence (monthly) and threshold (10%) are **conventions fixed here before
any run** — they are not tuned, and no variant of them is swept. Results are
reported as the honest range across R0/R1a/R1b, biased toward the
conservative reading.

## 2. Frozen measurement questions (verbatim scope from brief §3)

- **Q1 Gross carry** — funding received by the R0 position, zero costs.
  Per-year table 2020 → 2026-H1: annualized rate on notional, monthly
  mean/std, ASCII histogram of monthly gross carry.
- **Q2 Net carry** — Q1 minus costs, reported as a 3×3 grid:
  {R0, R1a, R1b} × {5, 10, 20 bps round-trip}. Both capital bases (§4).
  No "best" cell highlighted; no optimized cost figure.
- **Q3 Negative-funding episodes** — episode = maximal run of consecutive
  negative 8h funding intervals. Count, duration distribution (incl. longest
  run), cumulative negative carry per episode, calendar dates of the five
  deepest episodes.
- **Q4 Drawdown** — on the cumulative net-carry curve (funding + costs only;
  explicitly NO basis mark-to-market). Max drawdown and longest
  time-under-water, in % of notional and as multiples of average annual
  carry. Block-bootstrap CI on max DD: block length 90 funding intervals
  (30 days), 2,000 resamples, `random.Random(20260716)`.
- **Q5 Basis at position boundaries** — descriptive percentiles
  (1/5/25/50/75/95/99) of 1h spot-perp basis `(perp_close − spot_close) /
  spot_close`, full window and by year. Entry/exit haircut = basis paid
  entering at median vs 95th-percentile-adverse basis, reported in bps next
  to the Q2 grid (not folded into it).
- **Q6 Capacity/regime honesty check** — plain year-by-year mean funding
  table, isolated and labeled "is this shrinking?". No trend fit, no
  extrapolation.
- **Q7 Worst month / worst quarter** — of the net curve (10 bps cost cell,
  all three conventions), in plain dollars on $100k of total capital
  deployed (capital base ii of §3) and in %.

## 3. Accounting model

- **Funding cashflow**: at each 8h funding timestamp `t` (00/08/16 UTC),
  the short receives `rate(t) × contracts × price(t)`. Binance sign
  convention: positive rate → longs pay shorts (short receives). Sign is
  locked by the hand-verified fixture month (§7), not by trust.
- **Mark proxy**: `price(t)` = 1h perp close at `t`. This is a stated
  approximation of Binance's mark price at the funding snapshot.
- **Costs**: entry + exit round-trip (both legs) and R1 resize trades, at
  5 / 10 / 20 bps of traded notional. Slippage is inside the round-trip
  number, no separate model.
- **Capital bases** — every rate reported both ways:
  1. % of perp notional (pure carry rate);
  2. % of total capital deployed = spot notional + USDT margin buffer of
     **30% of notional** on the short leg. The buffer is a stated
     assumption; the liquidation math it implies is shown in the risks
     section against the worst historical rally in the data window.
- **No basis mark-to-market** in the P&L curve: the curve is funding minus
  costs. Basis effects appear only in Q5 as entry/exit haircuts.

## 4. Data (pinned inputs, frozen by hash)

| Series | File | State at spec time |
|---|---|---|
| Funding 8h | `cache/matrix/funding_BTC_USDT_USDT.csv` | verified clean: 7,119 pts, 2020-01-01 00:00 → 2026-06-30 16:00 UTC, strict 8h cadence, zero gaps |
| Perp 1h klines | `.backtest_cache/BTC_USDT:USDT_1h.csv` | verified clean: gap-free, 2020-01-01 → 2026-07-09 |
| Spot 1h klines | `.backtest_cache/BTC_USDT_1h.csv` | does not exist yet — created by the approved one-time fetch (below) |

- **Measurement window**: 2020-01-01 00:00 UTC → 2026-06-30 16:00 UTC
  (first → last funding point on disk). No refresh toward "today".
- **One-time spot fetch (approved amendment to the no-new-data rule)**:
  `tools/carry_measure_fetch_spot.py` calls the repo's existing
  `fetch_history("binance", "BTC/USDT", "1h", …)` once, writing the standard
  `OhlcvCache` file, then runs the same gap check applied to the other two
  series. Gaps or late start → stop-and-ask before anything else runs.
  Spot is used ONLY for Q5; funding accounting stays on perp marks.
- **Freeze**: after the spot fetch passes, the pipeline computes SHA-256 of
  all three CSVs and prints them in RESULTS.md and results.json alongside
  the pipeline commit hash. Run-once is enforced mechanically: the CLI
  refuses to run at all if RESULTS.md already exists.
- **Gap policy**: hard-fail on any missing 8h funding point or missing 1h
  bar inside the window. Never interpolate, never zero-fill. The check runs
  inside the pipeline even though the existing files already pass.

## 5. Outputs

- `experiments/carry_measure/RESULTS.md` — Q1–Q7 tables, risks section
  (§6), one-paragraph plain-language summary, no recommendation sentence,
  and the mandated final line verbatim:
  **"This is input to a personal investment decision, not a research
  verdict."**
- `experiments/carry_measure/results.json` — machine-readable mirror of all
  tables, input hashes, seed, commit hash.
- Histograms are ASCII/text — RESULTS.md stays a plain markdown file.

## 6. Risks section (mandatory prose, not modeled away)

1. **Exchange/counterparty tail risk** — both legs on one venue; an exchange
   failure is a total-position event historical funding data cannot price.
   Stated, not quantified.
2. **Liquidation risk on the short leg** — mechanics described; the 30%
   buffer assumption shown against the worst rally inside the data window
   (what rally would have exhausted it, and how close history came).
3. **Stablecoin/collateral risk** on USDⓈ-M margin.
4. **Spot-leg custody/borrow assumptions** — spot bought with own capital,
   held on-venue; no borrow. Stated as an assumption.
5. **Decay (Q6)** — past carry level is not a promise; the year-by-year
   table is the evidence, no extrapolation.

## 7. Code layout & tests

- `src/moonface/research/carry_measure.py` — pure stdlib accounting module:
  CSV loaders with gap validation, funding-cashflow engine, R0/R1a/R1b,
  cost model, episode detection, drawdown + block bootstrap
  (`random.Random(seed)`), monthly/quarterly aggregation, basis percentiles.
  No network imports; no I/O beyond reading the pinned CSVs.
- `tools/carry_measure.py` — thin CLI (repo convention: `sys.path.insert`
  then import `moonface.*`): computes and records input hashes, runs the
  module, renders RESULTS.md + results.json; refuses to run if RESULTS.md
  already exists.
- `tools/carry_measure_fetch_spot.py` — the one-time network script. Run
  once, by hand, before the pipeline.
- `tests/test_carry_measure.py` — `unittest.TestCase` via pytest:
  1. **Hand-verified fixture month** (D2 anchor): the earliest calendar
     month in 2021–2022 containing at least five negative 8h funding
     intervals (a deterministic selection criterion, applied before any
     P&L is computed). Gross and net carry hand-computed outside the code
     with the arithmetic shown in the fixture docstring; pipeline must
     reproduce it to rounding. Locks the sign convention; satisfies brief
     §6.4.
  2. Synthetic properties: zero rates → exactly zero gross carry;
     all-positive rates → gross = Σ rate×notional; constructed negative run
     → episode detector finds exactly it; flat prices → R0 ≡ R1a ≡ R1b;
     doubling costs never increases net carry.
  3. Gap guards: one missing 8h point → hard fail; one missing 1h bar →
     hard fail.

## 8. Execution protocol (order is part of the spec)

1. Implement module + CLI + tests; all tests green.
2. Run one-time spot fetch; gap check must pass (else stop-and-ask).
3. Single pipeline run.
4. If any result triggers brief §6.4 (surprising enough to suggest a
   convention error), verify against the hand-computed month before
   writing anything.
5. Write RESULTS.md + results.json once.
6. `gitnexus_detect_changes()`; commit. One run, one commit.
7. Re-runs only via a written amendment note in AMENDMENTS.md.

## 9. Stop-and-ask conditions (from brief §6, made concrete)

1. Funding-mechanics ambiguity that moves annualized results more than
   trivially (e.g. fixture month disagrees with hand computation).
2. Any temptation to add a timing/selection rule — stop, ask.
3. Data gaps per §4 (including in the freshly fetched spot series).
4. Surprising results per §6.4 of the brief — hand-verify first.
