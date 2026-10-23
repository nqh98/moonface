# Mandate assessment — where the most credible source of profitable futures signals is, 2026-07-28

Answers the standing mandate of `docs/findings/BACKLOG.md`: *"find the most
credible source of profitable futures trading signals."*

This is a **ranking of already-measured evidence**, not a new experiment. No
lane was re-run to produce it; every number is cited from a frozen artifact.
The arithmetic in §1.1 is read-only decomposition of the year table already
published in `experiments/vrp_measure/RESULTS.md` — that lane stays frozen and
its outputs are untouched.

## The one-line answer

**The variance risk premium (Deribit DVOL implied vs. subsequent realized) is
the most credible source, by a wide margin — and it is credible as a *measured
phenomenon*, not yet as a *tradeable signal*.** Nothing else in the program's
history has cleared a pre-committed threshold against properly-constructed
nulls. But the qualifier below is load-bearing enough that it changes what
should be done next.

## Why VRP wins the ranking, quantitatively

Every other candidate in program history was measured *at or below* its null.
VRP is the only one measured decisively above one:

| Lane | Best measured statistic | Against its bar | Verdict |
|---|---|---|---|
| **vrp_measure** | mean spread **+0.0949** | **9.49×** gaussian null p97.5, **4.70×** Student-t(4) null p97.5; both CIs strictly >0; 5/6 year buckets positive | **continuation TRUE — the only pre-committed threshold ever cleared** |
| positioning_transfer | DSR 0.933 (ETH) / 0.890 (SOL) | vs 0.95 gate | closest-ever miss, still fail; family terminal |
| oi_build (BTC) | DSR 0.30 | vs 0.95 gate | strongest single-asset result ever; noise |
| forced_flow COIN-M pilot | spread **0.60–0.67×** of both null p97.5 | below null | KILL, terminal |
| market_state_microscope | real 0.609 vs shuffle p95 0.835 | below null | INDISTINGUISHABLE_FROM_NULL |
| tda_topology | real 0.687 vs block-null p95 1.029 | below null | INDISTINGUISHABLE_FROM_NULL |
| bookdepth_study | +1.25 bps gross at h=1 | vs 10 bps cost → **net Z −5.2** | real, 10× under cost |

The gap is not marginal. VRP is roughly an order of magnitude clear of its
null; the runner-up families sit *inside* theirs.

### 1.1 The qualifier — and it is severe

Decomposing the published year table (`RESULTS.md` Q3) against the published
nulls (Q4):

| Sub-period | mean spread | n bars | × gaussian p97.5 | × Student-t(4) p97.5 |
|---|---:|---:|---:|---:|
| 2021–2026 (headline) | +0.094904 | 3790 | 9.49 | 4.70 |
| 2023–2026 | +0.045324 | 2494 | 4.53 | 2.24 |
| **2025–2026** | **+0.016284** | 1032 | 1.63 | **0.81** |

Three things follow, and only the third is already on the record:

1. **68.6% of the total spread-mass comes from 2021–2022 alone.** The headline
   +0.0949 is substantially a two-year regime, not a stationary premium.
2. **Over 2025–2026 the premium no longer clears the honest null.** It is
   1.63× the gaussian p97.5 but **0.81× the Student-t(4) p97.5** — i.e. below
   the fatter-tailed null that the SPEC itself called the more realistic one.
   On the bar the lane chose for itself, the recent period does not pass.
3. The lane already recorded the monotone decay. What it did not record is
   that the decay crosses the null boundary somewhere around 2025.

**Counter-caution against over-reading the decay:** the 2026 bucket is 302
12h bars ≈ 151 days ≈ **5.0 disjoint 30-day windows**. "2026 is negative
(−0.006)" is one badly underpowered bucket and is *not* an established kill.
2025 has only ~12.2 disjoint windows. The honest statement is "declining, and
recently indistinguishable from the fat-tailed null" — not "dead".

### 1.2 The structural problem VRP does not escape

`RESULTS.md` Q5: the five worst realized-variance windows (May-2021 crash) all
carry spread ≈ **−1.0**. The premium is collected in calm and repaid in
spikes. Harvesting it means being short variance — small steady gains, rare
large losses.

That is the program's drawdown wall wearing a new costume. The wall killed
`funding_fade` (+111R fixed-horizon drift against −100R to −277R research
drawdown) and every entry in `experiments/sizing/` (all three `chosen f = 0`,
terminal equity 1.0 at *every* fraction). There is no reason yet to believe
short-variance exposure is exempt, and one strong reason (Q5) to believe it is
not.

## The full ranking

| # | Candidate | Credibility basis | Blocker |
|---|---|---|---|
| **1** | **Variance risk premium** (DVOL) | only threshold ever cleared; 9.5×/4.7× nulls | decays below the t4 null by 2025–26; short-vol crash tail (Q5); no free per-strike data until ~2027-01 |
| 2 | `funding_fade` + `fixed_bracket` | OOS **+76.7R, +1.13R expectancy** — the program's best OOS number, rejected *only* by the absolute −15R cap | single entry, no null calibration of vrp's quality; frozen forward reg, trigger ~mid-2027 |
| 3 | Deribit **dealer gamma** | 0% overlap with any closed lane — genuinely new information set | entirely untested; option value only; readiness ~2027-01 |
| 4 | USDⓈ-M **liquidation** (Axis L) | 0% overlap, genuinely new | COIN-M pilot already KILL at 0.60–0.67× null → prior materially down-weighted; readiness ~2027-01-09 |
| 5 | `liqprem` (built 2026-07-28, unrun) | last untested premium class | weak prior — every other cross-sectional premium class died |

Everything below this line was measured at or inside its null and is closed.

## What this implies for the mandate

The mandate asks for the *most credible* source, and the answer is not "none".
It is VRP — but the credible claim is narrower than the headline number, and
the narrowing is what should drive the next decision:

- **The right next question for VRP is not "is it real?" but "is it still
  real?"** The full-window measurement answered the first. A Stage-1 spec
  should make the *decay* the primary object: does the premium survive on a
  sub-window that excludes 2021–2022, judged against the Student-t null, with
  a power check done in advance (the `matrix-step-a-router` lockbox was spent
  on an underpowered question — do not repeat that).
- **Cost-honesty must come before vehicle choice.** Per SPEC §0.3 that is
  Stage 1's job, and it now has a measured effect size to size its power check
  against — which is exactly the precondition the SPEC demanded.
- **`liqprem` should still be run.** It is built, one-touch, and its kill
  either way closes the cross-sectional space permanently. Cheap, terminal,
  and it removes the last residual ambiguity from the free-data question.

## What this assessment does not claim

No signal is promoted. Nothing is tradeable. The live stance remains WAIT, and
the participation advisor stays disabled — enabling it is a human decision.
VRP being the most credible *source* is a statement about where evidence is
strongest, not a statement that anything clears a trading bar. On the record,
nothing does.

## Sources

`experiments/vrp_measure/RESULTS.md` (frozen, commit `433aa2c`) ·
`docs/findings/PROGRAM_CONCLUSION.md` · `experiments/forced_flow/PILOT_VERDICT.md` ·
`experiments/microscope/` · `experiments/tda_topology/RESULTS.md` ·
`experiments/bookdepth_study/` · `experiments/sizing/20260609T175832Z/` ·
`docs/findings/BACKLOG.md`

---

# ADDENDUM 2026-07-29 — the answer has changed

Everything above was written on 2026-07-28. Three things happened the next day
that materially change the ranking. The original text is left intact; this
addendum supersedes its one-line answer.

## What changed

1. **`liqprem` ran and closed negative** (`fa36694`). It was the last of the
   three-hypothesis free-data addendum budget (`advval` KILL, `eventtime` KILL).
   Per the pre-committed terminal rule, **free data is now permanently
   finished** and the cross-sectional space closes with it.
2. **VRP Stage 1 was scoped and returned NOT WRITABLE**
   (`fad1d2a`, `experiments/vrp_stage1/SPEC.md`). Inverting the published
   disjoint CI gives sd ≈ 0.2586 per 30-day window. Confirming the 2025–26
   level (+0.0163) would need ~1009 disjoint windows = **82.9 years**; even ten
   years of forward collection gives MDE +0.0657, still 4× too coarse.
   **The premium has shrunk below the noise floor of its own estimator.**
3. **All three accruing evidence streams were found dead or empty**
   (`c55b250`). The liquidation collector had two bugs and **could never have
   written a row**; fixed and verified live at `b82a641` (132 rows in 75 s vs 0
   rows in 16 days). The other two remain pending human decisions.

## The revised one-line answer

**There is no credible source of profitable futures trading signals available
to this project today.**

That is a stronger and more useful statement than "VRP wins the ranking",
because the reason has changed. On 2026-07-28 the answer was *"VRP, but it is a
measured phenomenon rather than a tradeable signal."* On 2026-07-29 it is:

> VRP remains the best-measured phenomenon in the program's history and that
> measurement still stands for 2021–2026. But at its current size the premium
> **can no longer be distinguished from zero on any schedule this project
> operates on** — so it cannot be called credible as a *forward* proposition,
> only as a *historical* one. Stage 0 is not retracted; what is gone is the
> ability to act on it.

## What the mandate is actually blocked on now

Not research. Three of the four remaining routes are decided or dead:

| Route | Status |
|---|---|
| Free-data directional prediction | **closed, terminal** — 58 lanes, 0 hits |
| Free-data cross-sectional premia | **closed, terminal** — `liqprem` was the last |
| VRP harvesting | **not confirmable** at current size; needs execution the repo lacks |
| Deribit options chain (dealer gamma) | **the only 0 %-overlap untested source left** — and it has collected **1 day in 26** because its cron was never installed |

So the single highest-value action available to this program is not analytical.
It is installing a cron entry. That is an uncomfortable conclusion for a
research program, and it is the correct one.

## Standing guidance for the next reader

Do not answer the mandate by proposing a new signal family. Every such proposal
lands in the 0/58 column, and the reason is structural, not a shortage of
ideas: **the program has only ever asked prediction-shaped questions of free
price data, and that question is now exhausted in every direction it can be
asked.**

The two live options both change what the project *is* rather than what it
studies — acquire execution (unblocking risk-premium harvesting and Lane B), or
wait for genuinely new information to accrue (Deribit gamma, liquidations).
Both are human scope decisions. Neither is a research task.
