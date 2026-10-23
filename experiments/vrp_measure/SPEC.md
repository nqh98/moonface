# SPEC — `vrp_measure`: BTC Variance Risk Premium (Measurement Lane)

Status: DRAFT — awaiting human review before any implementation.
Source: AI-debate final proposal Lane A, 2026-07-17
(`ai-debate-lab/debates/20260717-find-a-new-strategy-or-a-genuinely-new-i/final.md`).
Design approved section-by-section in the brainstorming session of 2026-07-17.
Scope reduced from the source proposal by that session: Lane B (passive
execution alpha) is out of scope entirely; Lane A Stages 1–2 are out of scope
(see §0.2, §0.3).

## 0. Classification

### 0.1 What this lane is

- A **measurement lane**, under the same contract as `carry_measure` §0:
  descriptive accounting over historical data. Nothing is predicted.
- NOT a strategy, signal, or research registration. NO identity_hash freeze,
  NO EDGE FOUND / KILL verdict, NO entry/exit or sizing optimization.
- Forbidden scope creep (each voids the classification → stop-and-ask):
  - any predictive entry/exit condition ("sell vol only when …");
  - any parameter sweep whose objective is return maximization;
  - any output phrased as a trading recommendation;
  - any second RV estimator, second horizon, or second null added after
    results are seen.
- Anything worth computing that is not in Q1–Q6 after results are seen goes
  to `experiments/vrp_measure/AMENDMENTS.md`, never into the frozen run.

### 0.2 The one departure from `carry_measure`

`carry_measure` was pure description and stopped. This lane carries a
**pre-committed continuation threshold** (§6) that decides whether a Stage-1
spec is written.

This does not void the measurement classification. The threshold decides
whether *more research happens*, not whether anything trades. No promotion,
no signal, no position is gated on it. The distinction matters because
`carry_measure` measured a contractual cash flow whose existence was never in
question; this lane measures whether an effect exists at all, and its output
feeds a decision. The repo's failure history says that is exactly the moment a
number gets talked into being interesting after it has been seen — so the bar
is fixed here, in advance, in writing.

### 0.3 What is deliberately NOT here

- **Stage 1 (cost-honesty) and Stage 2 (pre-registered gate)** from the source
  proposal. Per `carry_measure` §0, a registered gate and a measurement lane
  cannot share a spec without voiding the latter. If §6 clears, Stage 1 gets
  its own spec, written with the measured effect size in hand so that its power
  check is real — the `matrix-step-a-router` lockbox was spent on a question
  that was never powered to answer it, and pre-registering a gate before
  Stage 0 reports would repeat that.
- **Any implementation vehicle decision** (DVOL futures, replicated variance
  swap, defined-risk options). Per-strike option data is confirmed
  unobtainable for free until the Deribit chain collector matures ~2027-01
  (`experiments/newdata/FREE_DATA_FEASIBILITY_deribit_options.md`). This lane
  needs none of it: the question is model-free.
- **Lane B (passive execution alpha).** `README.md:3-5` states there is no
  order execution, broker integration, or portfolio management anywhere in
  this repository. Lane B's own first check ("verify actual maker economics
  for the trading account") presupposes an exchange account this project does
  not have. Whether Lane B belongs in MoonFace at all is a human decision,
  recorded here as an open question and nothing more.

## 1. The question

Does BTC 30-day implied variance (Deribit DVOL) sit **persistently above** the
realized variance that follows it, over 2021-03-24 → 2026-05-31?

That is all. Not whether it is harvestable, not with what instrument, not at
what size, not net of what cost.

## 2. Corrections to the source proposal

The source proposal's Stage -1 was checked against the repo on 2026-07-17.
Three of its claims do not hold; the corrections are load-bearing and are
recorded here so the next reader does not re-derive them.

### 2.1 The DVOL fetch bug is real but was misdiagnosed

The proposal blames the no-forward-progress guard at
`src/moonface/research/exogenous/deribit_dvol.py:54`
(`if last < cursor + resolution: break`). That guard never fires.

Verified live against the Deribit API on 2026-07-17:
`public/get_volatility_index_data` returns **the most recent 1000 points**
inside the requested window, not the earliest. So the first page of a fetch
starting at 2020-01-01 already lands at the end of history; `cursor` jumps
past `end_ms`, and the loop exits having seen only the last 1000 points. This
is why `cache/exogenous/dvol_BTC_43200.csv` holds exactly 1000 rows spanning
2025-02-09 → 2026-06-24, and why `experiments/exogenous/STAGE01_RESULT.md`
reports `history_days: 499` (1000 points × 12h = 500 days).

**Fixing the guard would change nothing.** The fix is to paginate **backward**
on `end_timestamp`: fetch, take the earliest point of the page, set
`end = earliest - 1`, repeat until a page comes back empty.

Verified reachable output, 2026-07-17: **4 pages, 3837 points, back to
2021-03-24** — DVOL's actual inception. Not the "~2100+ days" the proposal
assumed; **1918 days**.

A second, independent bug in the same function: `resolution` is expressed in
**seconds** (43200 = 12h) but is added to **millisecond** timestamps in both
`cursor + resolution` and `last + resolution`. Both are corrected together.

### 2.2 The OHLCV acquisition step is already done

The proposal states there is no cached BTC OHLCV anywhere in the checkout and
budgets a Binance Vision fetch for it. There is. `carry_measure` fetched and
gap-verified both legs (`experiments/carry_measure/SPEC.md:102-104`):

- `.backtest_cache/BTC_USDT_1h.csv` — spot, 2020-01-01 → 2026-06-30, 56,945 bars
- `.backtest_cache/BTC_USDT:USDT_1h.csv` — perp, 2020-01-01 → 2026-07-09, 57,147 bars

Stage -1 therefore reduces to the DVOL fetch alone. No Binance Vision work.

### 2.3 The 7-day RV cross-check is dropped

The proposal asks for a 7d RV cross-check alongside the 30d. DVOL is a 30-day
constant-maturity index; DVOL vs 7d RV is not a horizon-matched IV−RV spread,
it is a different quantity. It is dropped rather than reported, because a
second horizon in a frozen run is a second implicit hypothesis, and
`exit-probe-results` closed on exactly that (its sole survivor was a
multiple-comparisons artifact).

## 3. Data (pinned inputs, frozen by hash)

| Series | File | State at spec time |
|---|---|---|
| DVOL 12h OHLC | `cache/exogenous/dvol_BTC_43200_full.csv` | **does not exist** — created by the one-time fetch (§3.2) |
| Spot 1h klines | `.backtest_cache/BTC_USDT_1h.csv` | exists; gap-checked by `carry_measure`; 12 spliced hours inside this window (§3.3) |

- `cache/exogenous/dvol_BTC_43200.csv` (the truncated 499-day file) is **not
  read, not modified, not deleted**. It is an artifact of the frozen
  `exogenous` lane and stays exactly as it is. The corrected history lands at
  a new path beside it.
- The perp series is **not used in this lane**. RV is measured on **spot**,
  because DVOL is derived from Deribit BTC options that settle on a
  spot-based index. Using perp marks would measure a different underlying.

### 3.1 Window

**2021-03-24 00:00 UTC → 2026-05-31 12:00 UTC.**

Frozen constants (exact, on-grid):

| Constant | Value | UTC |
|---|---|---|
| `WINDOW_START_MS` | `1616544000000` | 2021-03-24 00:00 |
| `WINDOW_END_MS` | `1780228800000` | 2026-05-31 12:00 |

- Left edge: first available DVOL bar (DVOL inception).
- Right edge, derived: `rv_var(t)` needs spot closes through `t + 720h`, i.e.
  the bar stamped `t + 719h` must exist. The last spot bar is 2026-06-30 16:00,
  giving `t ≤ 2026-05-31 17:00`. DVOL is the binding constraint on *grid*, not
  on span: **DVOL bars exist only at 00:00 and 12:00 UTC**, so the last usable
  `t` is the last grid point at or before that cap — `2026-05-31 12:00`.
  (An earlier draft of this section said 16:00, which is not a DVOL timestamp
  and therefore not a value `t` can take.) The last month of DVOL, through
  2026-06-24, is unusable by construction: no subsequent 30 days to compare to.
- **3790 DVOL bars** in the window. Spot bars required: 2021-03-23 23:00
  through 2026-06-30 11:00 (the leading bar supplies the close at `t`).
- Length: 1894.5 days = **64 disjoint 30-day windows** at phase 0. This is the
  lane's real sample size. It is small, and it is stated here before the run
  rather than discovered after it. (Where §4.3 and §7 say "n ≈ 63", the exact
  value is 64.)
- No refresh toward "today". The window is fixed at spec time.

### 3.2 One-time DVOL fetch

`tools/vrp_fetch_dvol.py`, run once by hand, mirroring
`tools/carry_measure_fetch_spot.py`. It:

1. calls the corrected `fetch_dvol` (backward pagination, §2.1) for
   `currency=BTC, resolution=43200`, walking back until a page returns empty;
2. hard-fails on any gap in the strict 12h cadence, or if the **fetched
   series' span** is shorter than 1900 days (expected 1918: 2021-03-24 →
   2026-06-24; distinct from the §3.1 measurement window of 1894.67 days,
   which is shorter because the last month of DVOL has no subsequent RV) —
   **stop-and-ask, do not proceed**;
3. **drops any incomplete trailing bar** — a bar stamped `t` is only complete
   once wall-clock `>= t + 12h` (verified: the API returns the currently
   forming bar, §4.1.1). Without this the fetch is not reproducible. The
   dropped bar is outside the §3.1 window regardless; the guard exists so a
   later re-fetch cannot silently disagree;
4. writes `cache/exogenous/dvol_BTC_43200_full.csv` in the same 5-column
   format as the existing file (`ts_ms, open, high, low, close`).

Expected: 3837 points, 2021-03-24 → 2026-06-24. A materially different count
is a stop-and-ask, not a shrug.

### 3.3 The spot splice

`tools/carry_measure.py` pins `SPOT_GAP_SUBSTITUTIONS_UTC`: 31 hours across 14
real exchange-side gaps, each spliced from the corresponding Coinbase BTC/USD
candle under a human-approved 2026-07-16 resolution, never interpolated.

Five of those dates fall inside this lane's window — **12 hours total**:

| Date (UTC) | Hours spliced |
|---|---|
| 2021-04-20 | 02:00, 03:00 |
| 2021-04-25 | 05:00, 06:00, 07:00 |
| 2021-08-13 | 02:00, 03:00, 04:00, 05:00 |
| 2021-09-29 | 07:00, 08:00 |
| 2023-03-24 | 13:00 |

`carry_measure` could discount this: spot fed only its descriptive Q5, and its
funding accounting never touched spot. **Here spot is the measurement.** Twelve
substituted hours out of ~45,000 is 0.03% and negligible on its own, but each
splice boundary creates an artificial Binance→Coinbase price step, and a
squared return is precisely what an RV estimator is built to notice.

**Policy:** a log return whose two endpoints straddle a splice boundary (i.e.
one endpoint is a substituted bar and the other is not) is **excluded from the
`Σr²` sum**, and that window's RV is scaled by its actual usable return count
`N` rather than an assumed 720. Returns wholly inside a run of substituted bars
are kept — they are Coinbase-to-Coinbase and carry no cross-exchange step. No
interpolation, no zero-fill, no window dropped. The excluded-return count per
affected window is reported in Q1.

### 3.4 Freeze and gap policy

- The pipeline computes SHA-256 of both pinned CSVs and prints them in
  RESULTS.md and results.json alongside the pipeline commit hash.
- Run-once is enforced mechanically: the CLI refuses to run if
  `experiments/vrp_measure/RESULTS.md` already exists.
- Hard-fail on any missing 12h DVOL point or any missing 1h spot bar inside
  the window other than the §3.3 substitutions. Never interpolate, never
  zero-fill. The check runs inside the pipeline even though the spot file
  already passed `carry_measure`'s.

## 4. Measurement conventions

All conventions below are **fixed here, before any run**. None is tuned, none
is swept, none has a variant.

### 4.1 Variance space is primary

- **Implied:** `iv_var(t) = (dvol_open(t) / 100) ** 2`, annualized variance.
  `dvol_open` is the **open** of the 12h DVOL bar stamped `t` (§4.1.1).
- **Realized** over `(t, t + 30d]`: hourly log returns on spot closes,
  `rv_var(t) = (Σ rᵢ² / N) * 8760`, where `rᵢ = ln(Pᵢ / Pᵢ₋₁)` and `N` is the
  count of usable returns after §3.3 exclusion.
- **Spread:** `vrp(t) = iv_var(t) - rv_var(t)`, annualized variance units.

Variance space is primary because it is what the claim actually is: a variance
swap pays on realized variance, and it is the model-free quantity DVOL is
constructed to price.

**Returns are not demeaned.** Variance-swap replication is on `Σr²`, not
`Σ(r − r̄)²`. This is a convention, stated, not an oversight.

- Annualization factor: **8760** hours/year (BTC trades 24/7/365).
- 30 days := exactly **720 hours**.

#### 4.1.1 Why `open`, not `close` — a look-ahead this spec originally had

The first draft of this section defined `iv_var(t)` from `dvol_close(t)`, "the
close of the 12h bar at `t`". **That is a 12-hour look-ahead** and is corrected
here.

Deribit's DVOL timestamps label the bar's **open**. Verified live 2026-07-17:
at wall-clock 06:28 UTC the most recent returned bar was stamped
`2026-07-17 00:00` — 6.5 hours old and still forming — and every bar's open
equals the previous bar's close (…36.32/36.32, 36.37/36.37), i.e. contiguous
12h bars stamped at their start.

So the close of the bar stamped `t` is not observable until `t + 12h`, while
`rv_var(t)` measures forward *from* `t`. Using it would let every one of the
~3730 measurements see 12 hours into its own RV window.

Because `open(t) == close(t − 12h)`, using the open costs nothing: it is the
same index value, correctly labeled, observable exactly at `t`. Causality is
then strict — `iv_var(t)` uses only information available at `t`, and
`rv_var(t)` uses only bars strictly after `t`. The window (§3.1) is unchanged.

This convention is robust to the timestamp question independently of the probe:
had `t` labeled the bar's *close*, `open(t)` would be the value at `t − 12h` —
merely stale, still causal. `close(t)` is a look-ahead under the true
convention. `open(t)` is safe under either.

### 4.2 One estimator

**1h close-to-close.** No Parkinson, no Garman-Klass, no 5-minute variant, no
second horizon (§2.3). Robustness variants go to `AMENDMENTS.md` after results
are seen; they do not enter the frozen run.

### 4.3 Sampling and the overlap problem

DVOL is 12h, so 30-day windows sampled at every DVOL point overlap 60-fold.
~3730 overlapping points carry roughly 63 independent observations.

**The primary statistic — `mean_spread` — is the mean of the overlapping
spread series.** Overlap does not bias a point estimate; it inflates the
apparent precision of one. So the point estimate uses every window, and every
interval claim about it is made by a method that accounts for the overlap.
This same definition is used for the real series and for both nulls, so the
null distribution in §5 is a distribution of exactly this statistic — which
means it absorbs the overlap penalty empirically rather than by assumption.

- The overlapping series' own **naive** standard error or t-statistic is
  **never computed or reported**. It would be wrong by roughly √60.
- **Primary CI:** block bootstrap over the overlapping spread series, block
  length **60 points (= 30 days**, matching the overlap horizon), **2000**
  resamples, `random.Random(20260717)`. Same shape as `carry_measure` Q4.
- **Cross-check CI:** disjoint 30-day windows at phase 0 from the window
  start, n = 64 (§3.1), plain two-sided 95% CI on their mean. Reported alongside its
  own mean, which will differ slightly from `mean_spread`.

### 4.4 Vol-point spread (secondary)

`dvol_open(t) - 100 * sqrt(rv_var(t))`, reported because vol points are how
volatility is read. **Descriptive only**, explicitly labeled as Jensen-biased
relative to the variance claim (`E[σ]² ≠ E[σ²]`). It is not part of any
threshold.

## 5. The null (the reason this lane is worth running)

### 5.1 Why the source proposal's null would not work

The proposal asks for "a synthetic/iid null (randomized-return-path resample
preserving DVOL's own marginal)."

Read as *iid constant-vol returns*, that null is vacuous here.
`vol_compression` compared a forward move against a **selected trailing**
estimator, so a constant-vol null broke the selection and the tautology
vanished — the null did real work (`experiments/vol_compression/RESULTS.md`).
DVOL is not derived from the return path at all; it is an exogenous market
price. Generate iid returns at an arbitrary constant vol, compare them to a
real DVOL series averaging ~60, and the resulting gap is whatever was baked
in. It would "show a spread" for reasons that say nothing, and a live lane
would be killed on an artifact.

### 5.2 The null this lane uses

**Null hypothesis, stated exactly: DVOL is a correct, unbiased statement of
BTC's instantaneous volatility, and no variance risk premium exists.**

Construction:

1. Take the pinned real DVOL series.
2. Build an hourly instantaneous vol path by holding DVOL piecewise-constant
   across each 12h bar: `σ(h) = dvol_open(t(h)) / 100 / sqrt(8760)`, where
   `t(h)` is the most recent DVOL bar stamped at or before hour `h`. Step
   function — no interpolation, matching how the data actually arrives, and
   using the same `open` convention as §4.1.1.
3. Generate synthetic hourly log returns `r(h) ~ N(0, σ(h)²)`, iid conditional
   on `σ`, and build a synthetic price path from them.
4. Run the **identical, unmodified pipeline** — same window, same §3.3 splice
   exclusions, same estimator, same `mean_spread` definition (§4.3) — on the
   synthetic path, against the **real** DVOL series.
5. Repeat over **500 seeds**, `random.Random(20270101 + i)` for `i` in
   `0..499`, yielding a distribution of `mean_spread` in a world where the
   premium is exactly zero by construction. (Base seed distinct from §4.3's
   bootstrap seed so the two procedures never share a stream.)

Whatever spread the pipeline reports under this null is **mechanical**: Jensen
convexity, the 12h-step vs 30d-window smoothing mismatch, annualization,
estimator noise, and the ~63-window sample.

**Test: the real mean spread must exceed the null distribution's 97.5th
percentile.** This subsumes bias correction rather than bolting it on — the
null distribution carries both the bias (its mean) and the sampling noise.
`real_mean − null_mean` is reported anyway, for interpretability.

### 5.3 The second, conservative null

Gaussian innovations give BTC no fat tails. Fat tails make realized variance
noisier, which **widens** the null distribution. A Gaussian null is therefore
**narrower than reality**, which makes it **easier** for the real spread to
clear — the null is generous to the lane, in the one direction this program
can least afford.

So a second null is run identically — same construction, same 500 seeds
(`random.Random(20280101 + i)`, again a distinct stream) — with
**Student-t(df=4)** innovations rescaled to unit variance (t(df) has variance
`df/(df−2)` = 2, so divide by `sqrt(2)`) and then scaled to the same `σ(h)`
path. `df = 4` is a convention pre-committed here: not estimated from the data
(which would make the null data-dependent), not swept.

**The real spread must clear the 97.5th percentile of both nulls.**

## 6. Continuation threshold (pre-committed, all three required)

1. **Null:** the real `mean_spread` (§4.3) > 97.5th percentile of **both** null
   distributions (§5.2, §5.3).
2. **Interval:** the block-bootstrap CI on `mean_spread` (§4.3) excludes zero
   **and** the disjoint cross-check CI excludes zero. Both must be strictly
   above zero, not merely non-straddling.
3. **Stability:** `mean_spread` computed within-bucket is positive in **at
   least 5 of the 6** calendar buckets (2021 partial, 2022, 2023, 2024, 2025
   complete, 2026 partial). Bucket membership is by the calendar year of `t`,
   not of `t + 30d`.

**Miss any one → the lane closes at Stage 0.5.** No Stage-1 spec, no parameter
rescue, no estimator retry, no window extension, no "it was close".

Honest reading of clause 3: it is a **fragility filter, not a significance
test.** Standalone, "≥5 of 6 positive" has a ~11% false-positive rate under a
true zero premium (7/64). It carries no statistical weight and is not intended
to. Its job is to catch the `macro-regime-instrument-results` failure mode,
where an effect exists only because one era dominates. Clause 1 carries the
significance.

Clause 3 was corrected during design: the brainstorming session initially
proposed "4 of 5 complete years 2021–2025" before establishing that DVOL
starts 2021-03-24, making 2021 a 9-month partial and leaving only four
complete years (2022–2025).

## 7. Frozen questions

Scope is locked to Q1–Q6. Anything else worth computing goes to
`AMENDMENTS.md`.

- **Q1 — Data integrity.** DVOL span, cadence check, point count, the
  499 → 3837 delta against the old cache; spot splice dates inside the window
  and the per-window count of excluded returns; SHA-256 of both pinned inputs;
  pipeline commit hash.
- **Q2 — The spread, full window.** Mean, median, distribution, and fraction
  of windows positive, in annualized variance. Block-bootstrap CI (primary)
  and disjoint-window CI (cross-check). Both the overlapping series (labeled
  descriptive) and the disjoint series (n = 64).
- **Q3 — Year-by-year.** Six calendar buckets, partials labeled as partial,
  each with its window count so thin buckets are visible.
- **Q4 — Null calibration.** Both null distributions over 500 seeds; the real
  spread's percentile in each; `real_mean − null_mean`. **This is the gate.**
- **Q5 — Tail behavior.** The five windows with the highest realized variance,
  their calendar dates, and the spread in each. A short-vol premium's entire
  risk is that it is collected in calm and repaid in spikes; a premium that is
  positive on average but deeply negative in every tail window is the single
  most important thing this run can report. **Descriptive — not part of §6.**
  Turning it into a threshold would be designing an exit rule, which voids §0.1.
- **Q6 — Vol-point spread.** §4.4. Descriptive secondary, Jensen caveat
  attached.

## 8. Components

| File | Role |
|---|---|
| `src/moonface/research/exogenous/deribit_dvol.py` | **modified** — backward pagination + seconds/ms unit fix (§2.1) |
| `tools/vrp_fetch_dvol.py` | **new** — one-time network script, run by hand (§3.2) |
| `src/moonface/research/vrp_measure.py` | **new** — pure functions; no network imports, no I/O beyond reading the pinned CSVs |
| `tools/vrp_measure.py` | **new** — thin CLI (repo convention: `sys.path.insert` then import `moonface.*`); hashes inputs, runs the module, renders RESULTS.md + results.json; refuses to run if RESULTS.md exists |
| `tests/research/exogenous/test_deribit_dvol.py` | **rewritten** (§9.1) |
| `tests/test_vrp_measure.py` | **new** (§9) |
| `tests/fixtures/vrp_measure/` | **new** — hand-checkable fixture series |
| `experiments/vrp_measure/{SPEC,RESULTS}.md`, `results.json` | outputs |

`src/moonface/research/vrp_measure.py` contents: CSV loaders with gap
validation, splice-aware return builder, RV estimator, spread, block bootstrap
(`random.Random(seed)`), calendar-year bucketing, both null generators,
percentile test, renderers.

### 8.1 Blast radius of the `fetch_dvol` change

`gitnexus_impact({target: "fetch_dvol", direction: "upstream"})` returned
`impactedCount: 0, risk: LOW` on 2026-07-17. **That result is wrong** — the
index is stale and missed three real references. Verified by grep, the callers
are:

- `tools/exogenous_btc.py:86` — the frozen `exogenous` lane's readiness CLI
- `tests/research/exogenous/test_deribit_dvol.py` — two tests

Actual blast radius: `experiments/exogenous/STAGE01_RESULT.md:30-34` states
DVOL is the *reserved* derived state and is **not screened in v1**, so the
frozen Stage-1 result does not depend on DVOL data. The fix changes a
**readiness number** (`history_days: 499` → ~1918), not a registered result.
`STAGE01_RESULT.md` is **not** retro-edited; the delta is reported in this
lane's Q1.

## 9. Testing

All tests hermetic. **No network in any test** — per the `confluence-engine`
non-hermetic test gotcha.

### 9.1 The DVOL regression test (the one that matters most)

`test_fetch_paginates_and_dedups` currently feeds `fetch_dvol` fake pages
ascending from `start` — it mocks an API that returns the **earliest** points
in the window. Deribit returns the **most recent** ones. The test encodes the
same wrong model as the code, so both agree and the bug is invisible. This is
the `aggressor-trades-rung0-build` fixture gotcha in a new place.

The rewritten test's fake **returns the most-recent-N window**, like Deribit
actually does. It **must fail against the current implementation** and pass
against the fix. Demonstrating that failure is a required step of the work,
not an optional nicety.

### 9.2 Known-answer RV

A synthetic constant-σ path must round-trip: `rv_var` recovers `σ²` within
tolerance. This is the only thing standing between an annualization error and
"the premium".

### 9.3 The rest

- **Splice exclusion** — a fixture containing a known splice boundary; usable
  return count `N` and resulting `rv_var` match hand-computed values.
- **Look-ahead guard** — assert no window reads a bar at or before `t`, and
  none reads past `last_spot`; assert `t_max = min(dvol_last, spot_last − 30d)`.
- **Determinism** — same seed → byte-identical outputs, for both nulls and the
  block bootstrap.
- **Null sanity** — the null pipeline on a constant-DVOL path returns a mean
  spread whose magnitude is small relative to the DVOL level (catches a sign
  error or a squared/unsquared mixup).
- **Gap policy** — a fixture with an unexpected missing bar raises, does not
  interpolate.

## 10. Error handling

Every failure is a hard stop. There are no fallbacks anywhere in this lane.

| Condition | Behavior |
|---|---|
| DVOL 12h cadence gap | stop-and-ask |
| DVOL span < 1900 days | stop-and-ask |
| Spot bar missing inside window, not in §3.3 | stop-and-ask |
| Input SHA-256 mismatch against recorded hashes | refuse to run |
| `RESULTS.md` already exists | refuse to run |
| Any window with `N` far below 720 usable returns | stop-and-ask |

No interpolation, no zero-fill, no silent skip, anywhere.

## 11. Run protocol

1. Fix `fetch_dvol`; rewrite its test; demonstrate the test fails against the
   old implementation and passes against the new one.
2. Run `tools/vrp_fetch_dvol.py` once, by hand. Cadence/span check must pass,
   else stop-and-ask.
3. Single pipeline run.
4. If any result is surprising enough to suggest a convention error, verify
   against the hand-computed fixture before writing anything.
5. Write RESULTS.md + results.json once.
6. `gitnexus_detect_changes()`; commit. One run, one commit.
7. Re-runs only via a written amendment note in `AMENDMENTS.md`.

## 12. Open questions (human decisions, not tasks)

1. **Lane B.** Does market-making research belong in MoonFace at all, given
   `README.md:3-5`? Its cheapest kill is a five-minute check the repo cannot
   perform: what maker fee tier does the trading account actually have? The
   source proposal assumes a rebate; Binance USDⓈ-M maker fee at non-VIP tiers
   is typically a ~2bps **cost**. If there is no account, there is no check,
   and Lane B is not a research question but an infrastructure decision.
2. **If §6 clears.** Stage 1 (cost-honesty under bid/ask haircuts) gets its own
   spec. The vehicle question (DVOL futures vs. replicated variance swap vs.
   defined-risk options) is answered there, not here.
3. **If §6 fails.** The lane closes. The corrected `fetch_dvol` and the
   1918-day DVOL history remain as reusable assets for any future lane; that
   is worth something regardless of the verdict.
