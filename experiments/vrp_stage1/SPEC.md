# SPEC — `vrp_stage1`: cost-honesty for the BTC variance risk premium

Status: **SCOPING COMPLETE — Stage 1 is NOT WRITABLE as a gate today.**
Written 2026-07-29. Chartered by `experiments/vrp_measure/SPEC.md` §0.3 and §12
("If §6 clears, Stage 1 gets its own spec, written with the measured effect
size in hand so that its power check is real").

This document *is* that power check. It is a separate directory so the frozen
`vrp_measure` lane is not touched; nothing here re-runs it, and every number
below is read-only arithmetic on its published CIs.

## 0. Classification

- A **scoping spec**. It answers one question: is a Stage-1 gate writable, and
  if not, under exactly what condition does it become writable?
- NOT a registration, NOT a gate, NOT an edge claim. No lockbox exists. No
  trading rule appears anywhere in this document.
- Its own conclusion (§4) is pre-committed in the sense that matters: it was
  derived from already-published numbers before any new data was fetched.

## 1. What Stage 1 was chartered to do

`vrp_measure` Stage 0 measured the premium and cleared its continuation
threshold: mean spread **+0.0949** annualized variance, **9.49×** the gaussian
null p97.5 and **4.70×** the Student-t(4) null p97.5, both CIs strictly above
zero, 5/6 year buckets positive.

Stage 1's chartered job was **cost-honesty**: does the premium survive bid/ask
haircuts, and through which vehicle (DVOL futures / replicated variance swap /
defined-risk options)?

`docs/findings/MANDATE_ASSESSMENT_2026-07.md` then reframed the priority. The
Stage-0 year table decays monotonically — +0.239 (2021) → −0.006 (2026 YTD),
with **68.6% of all spread-mass falling in 2021–2022**, and the 2025–2026
sub-period sitting at **0.81× the Student-t p97.5**, i.e. below the honest
null. So the prior question is not *"does cost eat it?"* but **"is there still
anything for cost to eat?"**

Both routes are examined below. Both close.

## 2. The mandatory power check

### 2.1 Recovering the estimator's dispersion

Stage 0 published a disjoint cross-check: n = 64 independent 30-day windows,
mean +0.126238, 95% CI [+0.062877, +0.189598]. Inverting:

```
SE  = (0.189598 − 0.062877) / 2 / 1.95996 = 0.032327
sd  = SE × √64                            = 0.2586
```

**One 30-day window's spread has sd ≈ 0.2586** in annualized-variance units.

*Validation of this back-out:* at the full-window level +0.094904 it predicts
`n = (2 × 0.2586 / 0.094904)² ≈ 30` disjoint windows to reach |Z| = 2. Stage 0
had 64 and returned a clean, decisive pass. The arithmetic is consistent with
the observed result, so the recovered sd is trustworthy.

### 2.2 A note on which CI governs

The block-bootstrap primary CI implies an *effective* n of **145.0**, but only
**63.9** disjoint 30-day windows exist in the 1918-day window. A resampling
scheme cannot manufacture more independence than the data contains: with 30-day
windows overlapping by up to 29 days, 30-day blocks do not fully break the
dependence, so the primary CI is **optimistic**.

**The conservative disjoint cross-check governs every number below.** This is
a correction to how Stage 0's headline CI should be read, and it makes the
conclusion *harder* to reach, not easier.

### 2.3 What it would take to confirm each measured level

| Sub-period | measured level | disjoint windows for \|Z\|=2 | calendar time |
|---|---:|---:|---:|
| full 2021–2026 | +0.094904 | 30 | **2.4 yr** — Stage 0 had 64 ✓ |
| 2023–2026 | +0.045324 | 130 | **10.7 yr** |
| **2025–2026** | **+0.016284** | **1009** | **82.9 yr** |

### 2.4 Minimum detectable effect going forward

80% power, α = 0.05 two-sided, forward-collected disjoint windows:

| forward horizon | n | MDE | vs the 2025–26 level (+0.0163) |
|---|---:|---:|---|
| 1 yr | 12.2 | +0.2077 | 12.8× too coarse |
| 2 yr | 24.3 | +0.1469 | 9.0× too coarse |
| 3 yr | 36.5 | +0.1199 | 7.4× too coarse |
| 5 yr | 60.8 | +0.0929 | 5.7× too coarse |
| 10 yr | 121.7 | +0.0657 | 4.0× too coarse |

**Even a decade of forward collection cannot resolve a premium of the size the
premium currently is.** The effect has shrunk below the noise floor of its own
estimator.

## 3. The second route: cost-honesty

Independently of §2, the chartered cost question is blocked twice over:

1. **Data.** Per-strike option quotes are confirmed unobtainable for free until
   the Deribit chain collector matures (~2027-01,
   `experiments/newdata/FREE_DATA_FEASIBILITY_deribit_options.md`). Bid/ask
   haircuts cannot be measured without them.
2. **Seat.** `README.md:3-5` — no order execution, no broker integration, no
   portfolio management. A cost-honesty study prices a fill this repository
   cannot make. This is the same infrastructure boundary that voided Lane B.

Neither is a research question. Both are decisions about what the project is.

## 4. Scoping verdict

**Stage 1 is NOT WRITABLE as a gate today**, on two independent grounds:

- the decay/level route is **not powered at any practical horizon** (§2.4);
- the cost-honesty route is **blocked on data and on execution** (§3).

Writing a registered gate now would repeat the `matrix-step-a-router` failure
exactly: a lockbox spent on a question the design was never powered to answer.
The correct output of a power check that returns NOT POWERED is to say so.

**This does not retract Stage 0.** The premium was real over 2021–2026 and the
measurement stands. What §2 establishes is narrower and worse: the premium is
now small enough that its *presence or absence can no longer be distinguished*,
and no amount of waiting fixes that while it stays this size.

## 5. Pre-committed re-entry condition

Stage 1 becomes writable **if and only if the premium recovers to a level that
is confirmable within a horizon the project would actually wait out.** Fixing
that horizon at 3 years gives MDE = +0.1199 (§2.4), so:

> **Trigger: the trailing-12-month mean IV−RV spread, computed on the same
> estimator as Stage 0 §Q2, reaches ≥ +0.12 and holds ≥ +0.12 for two
> consecutive quarterly checks.**

Rationale for the exact number: it is the 3-year MDE, not a round figure
chosen for looking reasonable. A premium below it cannot be confirmed on any
schedule this project operates on, so gating on anything smaller would be
theatre. For scale, +0.12 sits between the 2022 (+0.152) and 2023 (+0.065)
year means — i.e. the trigger asks for a genuine regime recovery, not noise.

**Monitoring discipline:**
- Quarterly, at most. Recompute from a fresh DVOL pull using the corrected
  backward-paginating `fetch_dvol`; the 12h grid and `dvol_open(t)` look-ahead
  fix from Stage 0 §2 both still apply.
- The monitor **must not write into `experiments/vrp_measure/`**. That lane is
  frozen; its RESULTS.md and results.json are final.
- A trigger firing licenses *writing a spec*, nothing more. It is not an entry
  signal and creates no position.

## 6. What would change this answer

Only these, and none of them is a new signal idea:

1. **The premium recovers** past §5's trigger. Checkable quarterly, cheap.
2. **A higher-frequency implied series** becomes available, giving more
   independent windows per year and therefore a lower MDE. DVOL is a 30-day
   index by construction; a 7-day implied series would change the estimand and
   would need its own spec and its own nulls — it is not a re-scope of this one.
3. **The project acquires execution** (§3.2). Then cost-honesty becomes a real
   study rather than a hypothetical, and the estimand shifts from "is the mean
   distinguishable from zero" to "does a live short-variance book have positive
   net expectancy" — a different question with different power properties.

Explicitly **not** on this list: conditioning the premium on a regime or state
to find a sub-window where it looks larger. That is the regime-conditioning
class, closed ~8 times, and `market_state_microscope` (n=1838,
INDISTINGUISHABLE_FROM_NULL) is the direct evidence against it. Slicing until
something clears is how the multiple-comparisons trap is entered, not exited.

## 7. Carried lessons

- **From `liqprem` (2026-07-29):** a threshold on sign alone licenses a stronger
  claim than the evidence supports. Every threshold in this document is paired
  with an explicit minimum-detectable-effect (§2.4, §5).
- **From `matrix-step-a-router`:** power-check before the lockbox, not after.
  This spec is that check, and it fired before anything was spent.
- **From `vol_compression`:** a valid gate must FAIL on an iid null. Any future
  Stage-1 gate inherits Stage 0's two nulls (gaussian and Student-t(4)) and
  must clear the Student-t one, which is the bar the 2025–26 sub-period already
  fails at 0.81×.
- **From Stage 0 §Q5:** the five worst realized-variance windows carry spread
  ≈ −1.0. Any future harvesting study must treat short-variance tail exposure
  as its primary risk, not as a footnote.

## 8. Status and next action

- **Status: SCOPED, NOT WRITABLE.** No registration, no lockbox, nothing spent.
- **Next action: none in this repository until §5's trigger fires or §6.3
  changes.** The quarterly monitor is optional and human-scheduled; skipping it
  costs nothing, because a premium that has fallen below its own noise floor
  does not become tradeable by being watched more often.
