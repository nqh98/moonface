# MoonFace Profit-Maximization Program — Conclusion

- **Concluded:** 2026-06-10
- **Status:** CLOSED by its own pre-committed stopping condition (no further classical/positioning probe warranted)
- **Instrument/data:** BTC, free OHLCV + funding, 3-year 4h window (and 1h where noted), anchored walk-forward with a one-touch OOS lockbox tail.

## Goal

Find a backtestable, out-of-sample-valid trading edge for the MoonFace BTC advisor —
maximize net R subject to a fixed risk gate: **trade_count ≥ 30, |research drawdown| ≤ 15R,
OOS-positive.** Falsification-first: one hypothesis per cycle, the OOS tail is the judge,
absolute survival required (beating a prior negative signal is not survival).

## What was tested (chronological)

| # | Cycle | Verdict |
|---|---|---|
| 1 | Diagnostics engine (SMC advisor, default gates) | Zero setups — gate cascade kills ~100% of windows; baseline −1380R, ~28% win. Full redesign indicated. |
| 2 | Edge probe, H1 (classical TA entries) | SMC-flip dead; breakouts show **positive fixed-horizon drift** but no OOS-valid bracket. "Exit is the lever." |
| 3 | Pivot confluence filters | 2/8 pass a *relative* rule; still negative OOS. Relative improvement ≠ absolute edge. |
| 4 | Exit probe, H1 | No `horizon_hold` clears the gate; lone `ma_cross+breakeven` survivor = multiple-comparison artifact. |
| 5 | Edge probe, H4 | Drift alive (donchian_break dominates); 3-entry set derived for exit search. |
| 6 | Exit probe, H4 | Drawdown kills every row (−16R to −153R vs 15R budget). No drawdown-acceptable edge. |
| 7 | Position sizing (H4 entries) | All 3 entries unsizable (chosen f=0). Moving drawdown from gate to sizing variable does not rescue the drift. |
| 8 | Funding-rate probe, H4 | fade/flip show horizon drift; all bracket-invalid. Drawdown wall is signal-independent. |
| 9 | Open interest | **Not OOS-testable** on free data (history capped ~30–90d). Shelved on feasibility, not falsified. |
| 10 | Spot-perp basis probe | REJECTED — all cells fail the OOS bracket gate. Last feasible non-price family → stopping condition B. |
| 11 | Positioning-entry exit probe | **Outcome A** — the cleanest-drift entries (funding_fade, basis pct=5) on the perp series, through the full fixed exit battery; no exit harvests the drift on ≥2 entries. |

Each cycle's detail lives in its `experiments/<family>/<timestamp>/` run and the matching
verdict memory.

## The single replicated finding

Across **every** family — price-derived (SMC, trend, breakout, range MR, pivots) and
positioning-derived (funding, basis) — and across both timeframes:

> **Positive fixed-horizon drift exists, but no bounded-risk exit harvests it within a 15R
> drawdown budget.** The drift is real and sometimes large (e.g. `funding_fade` held to a fixed
> horizon: OOS +1.63R expectancy, +111R net over 68 trades), but the unstopped hold incurs
> research drawdowns of −100R to −277R, and every stop/bracket/trail that bounds the drawdown
> either turns the edge negative or still violates the budget.

**The drawdown wall is structural to BTC and signal-independent.** It is not an artifact of one
signal family, one timeframe, one exit style, or the absence of position sizing — all of those
were varied and the wall held.

## Why the program stops here

The pre-committed stopping conditions both fired:
- **Condition B** (basis was the last feasible non-price family) — reached at cycle 10.
- **Outcome A** (the cross-entry exit search on the cleanest-drift entries found no robust
  survivor) — reached at cycle 11, the last untested combination of the program's only durable
  finding.

There is no further classical-TA or positioning probe whose result is not already implied. The
falsification program has exhausted its scope and returned a clear negative: **no robust,
absolute OOS edge exists on free BTC data under a 15R drawdown gate.**

## The one lever deliberately not pulled

Every cycle judged on an **absolute −15R drawdown cap**, held fixed for cross-cycle comparability
and overfitting discipline. The final run surfaced the program's most positive OOS result —
`funding_fade + fixed_bracket`: research net +64.7R, **OOS net +76.7R (+1.13R expectancy)** —
rejected *only* by that cap (research drawdown −32R) and by the single-entry robustness rule.

Whether that is a real, tradeable edge at a *proportionately larger* budget (judged on MAR/Sharpe
with matching position sizing) is the one open question this program did not answer, by design.
Pursuing it would be a **new program** with its own pre-committed discipline — not a continuation
of this one. It is recorded here as the sole data-motivated successor, not a recommendation.

## Artifacts

- Run leaderboards: `experiments/{diagnostics,edge,exits,funding,basis,positioning_exits,sizing}/`
- Reusable research engine: `src/moonface/backtest/edge/` and `src/moonface/backtest/diagnostics/`
- Per-cycle verdicts: the project memories (`*-results.md`).

## 2026-06-17 Reopening Closeout

The human-authorized new-mechanism reopening also closed negative: `bab`, `resrev`, `liqrev`, and `calseason` all failed their frozen gates. The remaining honest production stance is the WAIT advisor on free data. Further work requires a separately pre-registered new-data program, not more parameter search over the exhausted free-data axes.

## 2026-06-28 Structural escape route falsified (drift-basket)

The backlog's ground truth left exactly two credible moves that were not mere
parameter search: (a) confirm the strongest signal on independent data, and (b)
**change the portfolio structure so the wall no longer binds** (cross-sectional,
market-neutral). Route (a) closed negative as `positioning_transfer` (ETH DSR
0.933 / SOL 0.890 vs 0.95). Route (b) is now also closed:

> **`drift_basket` — CLOSED NEGATIVE 2026-06-28.** A single frozen beta-neutral,
> vol-targeted (0.20 annual, 5× cap), inverse-vol risk-parity basket of
> donchian-breakout drift legs over the survivorship-clean perp universe
> (monthly top-30), judged once through the standard 4-stage ladder on a daily
> return series (n_trials=1). Research net −0.64, Sharpe −0.05, DSR 0.017;
> stages 1–3 fail.

The decisive point is *how* it failed: **the diversification worked and the wall
held anyway.** Both honesty diagnostics came back clean — full portfolio beta
0.0027 and left-tail-to-BTC corr 0.0023 (the hedge genuinely neutralized BTC,
including in the drawdown tail), and distinctness-vs-momentum 0.11 (the legs are
a real time-series trigger, not cross-sectional momentum in disguise). So this
is not a broken hedge or a momentum artifact — a correctly-built market-neutral
overlay still produced no edge. The funding-cost accounting was deliberately
*lenient* (charged unscaled by leverage), biasing the result optimistic, so the
negative is conservative-credible.

Both structural escape routes are now exhausted. There is no remaining
pre-registered move whose result is not already implied; a genuinely new program
on new data would be required, not any v2 or variation of the closed families.
Detail: `experiments/drift_basket/` and the `drift-basket-results` memory.

## 2026-07-24 Final report — the July arc and terminal posture

After both structural escape routes closed (above), the program ran a large,
human-authorized second exploration wave through July 2026 and then converted to
a terminal, non-search posture. This section is the program-level synthesis of
that arc; per-lane detail lives in the `*-results` memories and each
`experiments/<lane>/` directory.

### 1. The second wave closed negative on entirely new axes

~30 further lanes were pre-registered and run across information sets the
06-10/06-28 conclusion had **not** touched — and every one returned negative or
indistinguishable-from-null. Representative closures:

- **Market-internal / breadth** — `breadth_thrust`, `breadth_internal` (v1/v2),
  `breadth_confirm`, `breadth_momentum_confirm`, `breadth_xasset`,
  `breadth_neutral`. Decisive result: the cross-asset transfer was **entirely
  crypto beta**, not independent alpha; the family closed 2026-06-28.
- **Regime selection / mixture-of-experts** — `regime_selector`,
  `regime_overlay`, `regime_mechanism_v3`, `regime_moe` (combiner + orthogonal
  experts), `market_state_microscope`. Forward-R does **not** stratify by regime
  (the microscope result explains ~8 dead regime lanes at once); macro/regime
  filters *subtract* return.
- **Scoring / calibration audits** — `calibration_diagnostic` (score
  UNCALIBRATED), `scoring_audit` (trend adequate / revert no-signal / pullback
  harmful), `trend_score_repair` (all repairs fail Gate 1).
- **Microstructure & ticks** — `aggtrades_hawkes` (killed), `bybit_trades`
  feasibility (best free tick source but fails as scoped), `book_depth` (effect
  real but ~10× under cost), `advval`, `eventtime`.
- **Macro / session / vol** — `macro_event` (FOMC/CPI), `macro_regime_instrument`
  (rank-flips across eras), `session_sweeps`, `vol_compression`
  (**key gotcha recorded: a valid gate must FAIL on an iid null**),
  `capitulation`, `euphoria_fade`, `sse`.
- **Geometric-signal program** — all six directions of the geometric research
  doc are now closed, culminating in `tda_topology_v1`
  (`INDISTINGUISHABLE_FROM_NULL`, 2026-07-16). See the closure table in
  `BACKLOG.md`; the block-vs-row null lesson there is load-bearing for any future
  market-level-label instrument.

The replicated finding of the original program held on every new axis: **no
robust, absolute OOS edge on free data** — the wall is signal-independent and now
demonstrated across price, positioning, breadth, regime, microstructure, macro,
and topological information sets (~80 closed domains total).

### 2. The one live candidate was withdrawn

The **MTF counter-trend lane** (1d/4h regime gate + 15m RSI dip-buy, 2-day hold)
was the program's strongest *live* result — the only signal to survive the
"no recent edge" killer — and was frozen for forward **paper** eval (never live;
it still failed DSR and the fixed-f drawdown cap in-sample). It was
administratively **WITHDRAWN on 2026-07-03** by the v2-only refocus mandate
(`docs/research-log/specs/2026-07-03-v2-only-refocus-design.md`): clock VOID,
0 completed forward trades, closed forever. A later planning prompt that assumed
this bot was still running is reconciled in `experiments/mtf/STATUS_2026-07-24.md`
— it is **not** running, and reviving the lineage would require a brand-new
registration, a human-only decision that has not been taken.

### 3. Terminal posture: no new search — only self-resolving forward tests and measurement

The program is not looking for new edges. Two disciplined, pre-committed
activities remain, both of which resolve on their own without further searching:

- **Frozen forward paper registrations** (accumulate out-of-time trades toward a
  one-shot verdict at a pre-set bar): `breadth_thrust:6` (underpowered, CONFIRM/
  REFUTE at pooled n≥30), `funding_fade_fwd` (SIGNED OFF & FROZEN 2026-07-14),
  Confluence **v2.2** (LIVE daemon; verdict pre-committed at 6mo / ≥30 setups —
  its at-freeze +40.14R is **not** evidence), and the `participation_advisor`
  (ships disabled; enabling is human-only). These are the honest way to power the
  few never-refuted-but-underpowered leads.
- **Descriptive measurement lanes** — explicitly framed as **personal-investment
  inputs, not forecasting edges**: `carry_measure` (delta-neutral funding-carry
  accounting, frozen one run 2026-07-16), `vrp_measure` (BTC variance risk
  premium; SPEC+PLAN only, build and fetch human-gated), `etf_rebalance`
  (Stage-0 → DEFER). They measure, they do not predict.

Forward data infrastructure is human-operated, not autonomous: the Deribit chain
collector (LIVE 2026-07-03) and the USDⓈ-M liquidation + Deribit-gamma doors
(open ~2027-01 after `forced_flow` COIN-M kill 2026-07-14) accrue only when a
human runs them — the collector manifests must be checked, never assumed.

### Bottom line

The free-data directional-edge search is exhausted and confirmed negative across
every credible axis. The remaining honest production stance is the **WAIT
advisor**. The program now does exactly two things and starts nothing new: it
lets a handful of frozen registrations accumulate paper trades toward
self-resolving verdicts, and it measures market structure (carry, VRP) to inform
personal allocation. Any genuinely new edge work requires a **separately
pre-registered new-data program** — not a v2, retune, or variation of any closed
family.
