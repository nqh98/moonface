# liqprem — interpretation note

Written after the frozen run of 2026-07-29. **The verdict in `verdict.json` /
`report.md` is unchanged and stands.** This file records what the number does
and does not license, so the next reader does not over-read it. It is a
separate artifact by design — the frozen outputs are not edited.

## What ran

- 787 archived USDT perps discovered; **772 had data** in the frozen window
  (2023-07-29 → 2026-07-28); **434 cleared the viability floor** (listed ≥365d
  AND trailing-30d median dollar volume ≥ $1M).
- 434 members ⇒ **86 symbols per leg** — a well-diversified quintile book, and
  a far wider illiquid tail than the top-20 universes of `xsection`/`resrev`/
  `bab`. The minimum-viability floor did the job it was designed for.

## The result

| | mean/day | Stouffer Z |
|---|---:|---:|
| gross (zero fee) | −0.00010666 | **−0.2802** |
| net (25/5 bps asymmetric) | −0.00015442 | −0.4055 |

Kill branch **`no_premium`** fired: pre-registered rule is *gross Z ≤ 0 ⇒ no
liquidity premium in this cross-section*. −0.2802 ≤ 0, so the rule is satisfied
exactly as written and the lane is closed.

## What this does NOT say

**It does not say illiquid perps underperform.** |Z| = 0.28 sits dead centre of
the null. The point estimate is negative, but a coin flip produces |Z| ≥ 0.28
about 78% of the time. The honest reading is *no effect detectable in either
direction*, not *reversal*.

**It is not a high-powered exclusion of a small premium.** Effective research
window ≈ 511 days (876 days minus the ~365-day warmup during which the listing-
age floor leaves the universe empty — a structural property of the frozen
design, noted pre-run in commit `f7f78a1`):

| n (daily obs) | mean/std needed for \|Z\|=2 | ⇒ annualized Sharpe |
|---:|---:|---:|
| 511 (effective) | 0.0885 | **≥ 1.69** |
| 876 (full window) | 0.0676 | ≥ 1.29 |

So the test could only have detected a premium worth roughly **Sharpe ≥ 1.7**.
A real-but-modest illiquidity premium (say Sharpe 0.4–0.6) would have been
invisible to it. Absence of evidence here is weak evidence of absence.

## The weakness this exposes in the pre-registration

The kill rule was written as a **threshold on sign** (`Z ≤ 0`), not on
significance. That makes it decisive and un-gameable — which is why it was
written that way — but it means the rule licenses the sentence *"no liquidity
premium exists in this cross-section"* on evidence (|Z| = 0.28) that cannot
support a claim that strong.

Recorded as a finding about the instrument, **not** as grounds to reopen the
lane. The rule was frozen before any data look, it fired, and the lane is
closed. Future preregistrations in this repo should pair a sign threshold with
a minimum-detectable-effect statement so that a null result carries its own
power caveat instead of needing one bolted on afterwards.

## Programme consequence

`advval` KILL (2026-07-06) · `eventtime` KILL (2026-07-06) · `liqprem` KILL
(2026-07-29). All three hypotheses of the free-data addendum are closed.

Per the addendum's pre-committed terminal rule, **free data is now
unconditionally and permanently finished** — no reopening under any framing.
The cross-sectional space is closed with it: momentum, carry, BAB, residual
reversal and now illiquidity have each been tested and killed.

The program's only remaining forward paths are the frozen paper threads and the
maturing new-data collectors (Deribit options readiness ~2027-01, USDⓈ-M
liquidation ~2027-01-09). Standing stance is unchanged: WAIT, advisor disabled.

See `docs/findings/MANDATE_ASSESSMENT_2026-07.md` for where the surviving
evidence actually is.
