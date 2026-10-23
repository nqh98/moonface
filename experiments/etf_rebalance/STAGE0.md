# etf_rebalance — Stage 0 Feasibility (Month-End Forced Rebalance Flow)

- **Date:** 2026-07-16
- **Lane status:** Stage 0 executed per the human brief (2026-07-16). **No registration
  frozen, no pilot code written, no lockbox opened, no hypothesis-window returns touched.**
- **OUTCOME (exactly one): `DEFER (dated 2029-04-01)`** — Checks A and B pass; Check C's
  pre-committed stop condition fires (MDE at today's n exceeds the entire plausible-effect
  range). Earliest defensible powered date = after the 2029-03 month-end under the
  favorable-end anchor; central-anchor date ~2040-11; unfavorable-end date is never
  (2087+). Full dating logic in §4; what the deferral authorizes in §5.

---

## 0. Scope, authority, and hygiene ledger

Stage 0 decides only whether a pre-registered pilot is justified. It tests nothing,
produces no verdict on the hypothesis, and no trading rule. `DEFER` pre-authorizes exactly
one thing: a re-run of this Stage 0 at the dated point (or on an early-trigger in §5).
`PROCEED` was not reached; nothing else is authorized.

**Data touched (hygiene rules §4 of the brief):**

- Check A: existing closed-lane documents and verdicts only.
- Check B: public web figures (all cited in §6) plus **one volume-only read** of the repo's
  Binance kline cache (`cache/matrix/BTCUSDT_4h.csv`, dollar-volume column, June/H1-2026
  aggregates) as a sanity floor for the ADV denominator.
- Check C: calendar counts from cache coverage timestamps; volatility estimated from
  **pre-2024 closes only** (2020-01-01 → 2023-12-31, explicitly permitted by the brief).
- **NOT touched:** any ETF-era (≥2024-01) return series, any month-end window return, any
  join of calendar coordinates to returns, the conditional relationship itself. The forward
  data remains clean for a potential future registration.

**Program standing.** This is a new-mechanism Stage-0 (forced dollars on the TIME axis,
five-condition framework — the `forced_flow` lineage), human-authorized by the brief. It is
not a reopening of `calseason` parameter search and not a claim against the free-data
addendum's terminal rule; post-addendum practice (forced_flow, macro_event, tda_topology)
is that human-authorized new-mechanism Stage-0s are legitimate and each must clear its own
overlap audit — which is what §2 does.

## 1. Hypothesis (context only; NOT tested here)

Since US spot BTC ETFs launched (2024-01), BTC sits in model portfolios with target
weights. Calendar mandates force rebalancing: if BTC outperformed the rest of the portfolio
intra-month, allocators must SELL near month-end to restore weights, and vice versa.
Prediction (for a future pilot only): BTC returns in a defined month-end window correlate
negatively with BTC's intra-month relative performance, ONLY in the ETF era (≥2024-01) and
not before — the pre-2024 non-effect is a built-in placebo. Five-condition framework:
mandatory ✓ / locatable in time ✓ / persistent at 1h+ ✓ / size = §3 / not-yet-digested =
partially open (BTC leg ~2.5y old; equity turn-of-month effects are heavily front-run).

## 2. Check A — Overlap audit vs the closed-lane record

Standard applied: the repo's Axis-F standard (`docs/research-log/concepts/price_axis_geometry_AUDIT.md` §2):
**≥50% *mechanism* overlap (same underlying causal claim) with an existing verdict → VOID.**
Feature overlap alone does not void.

| Prior record | What it actually tested | Overlap with this claim | Ruling |
|---|---|---|---|
| `calseason` (CLOSED NEGATIVE 2026-06-17) | 4 **fixed, unconditional** calendar cells — funding-settlement hours {pre,post} and weekend/weekday — pooled over 16 alt perps with **BTC/ETH/SOL excluded**; its preregistration ruled months/holidays/sessions **inadmissible in that cycle** | No month-end cell, no conditioning variable, no BTC, no era contrast. The one shared ingredient (calendar coordinates) carries **no sign information** in this hypothesis — the predicted sign flips with the intra-month gap, a variable calseason never measured | **<50%** |
| `price_axis_geometry_AUDIT` C8-calendar (VOID 2026-07-14) | "Calendar-time pressure" as an **unconditional time-axis accumulator** (pressure per interval, no mass term), voided ≥50% *via calseason coverage* | The C8 construct is exactly the unconditional claim calseason killed. This lane's mass term = mandated AUM × intra-month relative-performance gap — a conditioning mass no covering record contains. Read maximally ("anything calendar is void") C8 would cover this; read by its own standard (same causal claim) it does not: performance-conditioned forced flow with an era placebo was never tested. We state both readings rather than lawyer the narrow one; the audit's own definition governs | **<50%** |
| `macro_event` (closed_negative 2026-07-03) | FOMC/CPI **event windows** — calendar-located, unconditional direction, no era placebo | Different calendar coordinates, no performance conditioning, mechanism = event risk not forced flow | <50% |
| `session_sweeps` (FAIL sealed OOS, 2026-07-08) | **Intraday session** partition, unconditional | Different coordinates and no conditioning | <50% |
| `xsection` mom_30 (CLOSED 2026-06-12) / breadth family (CLOSED 2026-06-28) | Conditioning on **relative performance** as cross-sectional selection / breadth, no calendar-flow mechanism, no month-end window | Shares only the conditioning-variable *family*; the causal claim (mandated calendar flow) is absent | <50% |
| `forced_flow` (COIN-M KILL 2026-07-14; construct table C1–C10) | Liquidation wells (price axis) and funding bleed (time axis) | Same mechanism **class** (forced dollars), different force: calendar-rebalance mass appears nowhere in C1–C10 except the unconditional C8 row above | <50% |
| `universe_donchian` monthly reconstitution | Operational rebalance of a test universe, not a hypothesis | — | 0% |

**Result: no covering verdict at ≥50%. Check A passes.** The honest distinction, recorded
per the brief: the program has swept *unconditional* calendar seasonality (and killed it);
it has never tested a **performance-conditioned, era-scoped (≥2024-01 with pre-2024
placebo), BTC-specific** calendar-flow claim. The conditioning variable is not a refinement
of calseason's partition — it is the entire content of the prediction.

## 3. Check B — Size / plumbing (public figures only)

### 3.1 Inputs (sources in §6)

| Quantity | Value carried | Source, date |
|---|---|---|
| US spot BTC ETF AUM | **$74.8–77.7B**; top reading rounded to $78B | SoSoValue via KuCoin (close 2026-07-13); CoinGlass (accessed 2026-07-16) |
| IBIT AUM | ~$44.9B | Investing.com (early July 2026) |
| 13F-reported share of ETF AUM | 20.8% (Q1-2026), 24.7% (Q4-2025), 24% (Q3-2025), 22.9% (Q1-2025) | CoinShares 13F reports |
| Advisor share of 13F assets | 50% (Q1-2025) → 57% (Q3-2025) | CoinShares |
| Advisor behavior | strategic model-portfolio allocations, 1–10% weights, "rebalance on schedule" | CoinShares/ETF Trends; Blockworks |
| ETF secondary volume | IBIT ~$2B/day typical, $3B busy, $10B record; IBIT ≈ 73.7% of ETF volume → complex ≈ **$2.7–4B/day** | Bloomberg via Yahoo; The Block |
| Spot ADV floor | Binance BTCUSDT perp dollar ADV **$12.8B/day (June 2026)**, $12.5B (H1-2026) — volume column only, repo cache of public Binance data | computed 2026-07-16 |
| Global spot+ETF ADV range carried | **$18B (low) / $28B (central) / $44B (generous)** | constructed from the two rows above; The Block/Statista magnitudes paywalled |

**Rebalance-share range (the weakest number, constructed, range carried):** no direct
published estimate of "share of ETF AUM in calendar-rebalanced wrappers" exists. From the
13F decomposition: advisor-held ≈ (20.8–24.7%) × (50–57%) ≈ **10–14% of total AUM**.
Carried range **5%** (only half of advisor-held on calendar mandates) to **25%** (all
advisor-held plus an equal invisible sub-$100M-advisor mass — 13F only captures filers).

### 3.2 Arithmetic

Flow = share × AUM × |gap| × (1−w), w≈3% → factor 0.97. (For calibration: with pre-2024
monthly gap σ ≈ 19.3%, E[|gap| given |gap|>5%] ≈ 18.7%, so the brief's "large" 15% month is
typical of qualifying months, not extreme.)

| Scenario | Flow |
|---|---|
| modest move 5%, bottom share 5% | $0.19B |
| modest move 5%, top share 25% | $0.95B |
| large move 15%, central share 12% | $1.36B |
| **large move 15%, top share 25% (kill-test numerator)** | **$2.84B** |

Kill test (per brief: CLOSED only if <1% of month-end-window volume even at large move ×
top share; per hygiene rule 3 the denominator uses the **generous** volume reading, which
makes survival hardest):

| Window | Volume (generous reading: $40B/d spot + $4B/d ETF) | Flow ratio |
|---|---|---|
| 72h | $132B | **2.1%** |
| 24h | $44B | **6.4%** |

**2.1% ≥ 1% → NOT closed-too-small. Check B passes.** At central volume the 72h ratio is
3.4%; at 24h, 10.1%.

### 3.3 Flow-timing (smearing) caveat, as a number

Advisory-platform rebalances execute as boundary-day orders, but AP/issuer primary-market
mechanics settle T+1 and issuers may work flow via TWAP/OTC. For the kill-test numerator to
fall below the 1% bar, the fraction of mandated flow executing **outside** the 72h window
must exceed **53%** (generous-volume denominator) to **81%** (low-volume denominator).
I.e., the effect survives Check B unless more than roughly half-to-four-fifths of the
forced flow is smeared away from the month boundary. This is the single biggest plumbing
unknown and is flagged as pilot-design-relevant (§4.4).

## 4. Check C — Power (design math only; no ETF-era returns touched)

### 4.1 Sample and buckets

Month-ends 2024-01 → 2026-06: **n = 30** by calendar (29 windows complete in the repo
cache, which ends 2026-06-30 20:00 UTC; the June window's forward side is public and a
trivial refresh). Accrual: +12/year.

Conditioning distribution (design math from pre-2024 vol, not measured ETF-era data):
monthly gap σ ≈ √(19.17² + 2.5²) ≈ 19.3% (BTC pre-2024 monthly vol; 60/40 portfolio ~2.5%,
independence assumed). Bucket estimates at n=30: threshold ±5% → **~11.9 per tail**, ~6.1
neutral; threshold ±10% → ~9.1 per tail, ~11.8 neutral. Calcs below use the ±5% threshold.

### 4.2 Vol figures and MDE

Pre-2024 BTC vol from cache 4h closes (2020-01-01 → 2023-12-31): σ(4h) = 1.429% → daily
3.50%, 12h 2.47%, 48h 4.95%, 72h 6.06% (√-scaled). Repo-standard confidence: two-sided
α = 0.05, power 0.80 → MDE = 2.8 × σ_w × √(2/n_tail) for the between-bucket difference.

| n (date) | ~n/tail | 12h | 24h | 48h | 72h |
|---|---|---|---|---|---|
| 30 (today) | 11.9 | 2.84% | **4.01%** | 5.67% | 6.95% |
| 36 (+6m) | 14.3 | 2.59% | 3.66% | 5.18% | 6.34% |
| 42 (+12m) | 16.7 | 2.40% | 3.39% | 4.79% | 5.87% |
| 54 (+24m) | 21.5 | 2.11% | 2.99% | 4.23% | 5.18% |

### 4.3 Plausible-effect anchor (from the Check-B flow-to-volume ratio, assumption stated)

Square-root impact law, ΔP = Y·σ_daily·√(Q/ADV), Y = 1 (linear alternative shown). The
detectable quantity is the **between-bucket difference ≈ 2× single-sided impact** of a
typical qualifying (15%-gap) month:

| Anchor | share | ADV (incl. ETF) | Q | sqrt-law diff | linear-law diff |
|---|---|---|---|---|---|
| favorable | 25% | $18B | $2.84B | **2.78%** | 1.10% |
| central | 12% | $28B | $1.36B | **1.54%** | 0.34% |
| unfavorable | 5% | $44B | $0.57B | **0.80%** | 0.09% |

(The favorable ADV is floored at the *measured* $12.8B Binance-perp figure plus minimum
spot/ETF increments — an ADV below the measured floor is not defensible.)

### 4.4 Decision

**The stop condition fires.** MDE at today's n exceeds the ENTIRE plausible range at every
window: 24h MDE 4.01% > 2.78% (favorable top). Even the most aggressive corner — a 12h
window granting **full** flow-and-impact concentration inside it — gives MDE 2.84% > 2.78%.
There is no defensible PROCEED reading at n = 30. Per the pre-committed rule:
**DEFER (dated)**.

**Dating logic (readings considered, per hygiene rules 3–4):**

- Powered-at, 24h window (boundary-day concentration — supported by platform plumbing, no
  extra unevidenced assumption): favorable anchor → **63 month-ends → after the 2029-03
  month-end → re-run 2029-04-01**; central → 2040-11; unfavorable → 2087+ (never, in
  practice).
- The 12h-window branch would be powered at ~32 month-ends (~2026-09) under the favorable
  anchor, but ONLY with evidence that mandated flow concentrates intra-day; rule 3's
  unfavorable end on that unmeasured concentration kills the branch today. It is recorded
  as the one design lever that could legitimately pull the date forward (§5).
- The brief's instruction is "the earliest date at which n makes the pilot powered": that
  is the favorable-anchor 24h reading → **2029-04-01**. The range is carried, not hidden:
  under the central anchor this deferral is **close-equivalent** (2040-11), and under the
  unfavorable anchor or the linear impact law the pilot is never powered. A human reading
  this should weigh the DEFER as "cheap dated re-check, prior unfavorable," not as
  "expected to pass in 2029."
- These readings move the *date*, not the *state* — every reading lands on DEFER, so the
  stop-and-ask clause (brief §4.4) is not triggered.

## 5. Outcome and what the deferral does

**`DEFER (dated 2029-04-01)`.**

- **Pre-authorized:** re-running this Stage 0 (all three checks, fresh figures) on or after
  2029-04-01. Nothing else — no data peeking, no pilot draft, no registration.
- **Early re-run triggers (any one):**
  1. Published, citable evidence that platform rebalance flow concentrates intra-day near
     the boundary (enables the 12h design → powered under the favorable anchor from
     ~2026-09 onward). Gathering such plumbing evidence from public documents touches no
     price data and is permitted anytime.
  2. US spot BTC ETF AUM sustained ≥ ~2× the current $78B (effect scales ≈ √AUM under the
     sqrt law), or a direct published estimate of the calendar-rebalanced share materially
     above the 25% top-of-range.
  3. n-accrual reaching the favorable-anchor powered count early is impossible (calendar
     time is the clock), but a redesigned estimator (e.g., continuous-gap regression rather
     than bucket difference) may be proposed at re-run — it requires a fresh Stage-0 power
     section, not this one.
- **What accrues meanwhile:** +12 month-ends/year (n=63 needed at the favorable anchor);
  AUM/share/volume figures evolve; the mechanism ages (equity-market precedent says
  month-end effects get front-run — the "not-yet-digested" condition decays with time,
  which is a reason NOT to expect the 2029 re-run to improve on the anchor).
- **Calendar hook:** HUMAN OPS (repo precedent: cron/calendar reminders are human-installed).
  Suggested entry: `2029-04-01 — re-run experiments/etf_rebalance/STAGE0.md checks; brief
  2026-07-16; early triggers in §5.`

## 6. Sources (accessed 2026-07-16)

- SoSoValue data via KuCoin News flash, 2026-07-13: total US spot BTC ETF net assets
  $74.79B; $424.66M daily outflow. <https://www.kucoin.com/news/flash/us-spot-bitcoin-etfs-record-424-66m-outflow-on-july-13-2026>
- CoinGlass Bitcoin ETF dashboard: combined AUM $77.7B / 1,212,532 BTC. <https://www.coinglass.com/etf/bitcoin>
- Investing.com, "Bitcoin's July ETF Reversal…" (July 2026): IBIT ≈ $44.91B AUM. <https://www.investing.com/analysis/bitcoins-july-etf-reversal-faces-a-tough-test-after-junes-exodus-200683924>
- CoinShares Bitcoin 13F Q1-2026 report: 13F filers = 20.8% of total US BTC ETF AUM (down
  from 24.7% Q4-2025). <https://coinshares.com/pl-en/insights/research-data/bitcoin-13f-q1-2026-report/>
- CoinShares 13F Q3-2025: filers = 24% of AUM; advisors = 57% of 13F assets. <https://coinshares.com/insights/research-data/13f-filings-of-bitcoin-etfs-q3-2025-institutional-report/>
- CoinShares 13F Q1-2025: institutions 22.9% of $92B AUM; advisors 50% of 13F assets. <https://coinshares.com/us/insights/research-data/13f-filings-of-bitcoin-etfs-q1-2025-institutional-report/>
- Blockworks, "How are advisers using bitcoin ETFs in client portfolios?": 1–10%
  allocations, scheduled rebalancing. <https://blockworks.co/news/advisers-bitcoin-etfs-client-portfolios>
- ETF Trends / CoinShares channel, "Advisors Are Betting Big on Bitcoin": advisor
  model-portfolio behavior. <https://www.etftrends.com/coinshares-channel/advisors-betting-big-bitcoin/>
- Bloomberg via Yahoo Finance: IBIT $10B single-day volume record; ~$2B/day typical, $3B
  busy. <https://finance.yahoo.com/news/blackrock-spot-bitcoin-etf-posts-231730548.html>
- The Block ETF volume data: IBIT ≈ 73.7% of spot-ETF volume. <https://www.theblock.co/data/etfs/bitcoin-etf/bitcoin-spot-etf-volumes>
- Binance BTCUSDT perp dollar ADV June-2026 $12.8B/day: computed 2026-07-16 from the repo's
  Binance Vision kline cache, volume column only (public exchange data).
- Repo internal (Check A): `experiments/calseason/PREREGISTRATION.md` + `report.md`;
  `docs/research-log/concepts/price_axis_geometry_AUDIT.md`; `experiments/macro_event/report.md`;
  `experiments/session_sweeps/RESULTS.md`; `experiments/forced_flow/STAGE0_FEASIBILITY.md`
  + `PILOT_VERDICT.md`.
