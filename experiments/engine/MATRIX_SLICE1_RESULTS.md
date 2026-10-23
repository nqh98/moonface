# Signal Matrix — Slice-1 Registered Run Results

**Date:** 2026-07-07
**Verdict:** `CLOSED_NEGATIVE_VALIDATION`
**Report:** `experiments/engine/matrix_slice1_2026-07.json`
**Registration:** `experiments/engine/MATRIX_SLICE1_REGISTRATION.md` (frozen, pre-run)
**Sealed BTC year:** **NOT opened** (Gate 1 failed → gate2/gate3 null). Bullet intact.

## Result

| metric | value | gate |
|---|---|---|
| validation n | 8 | ≥ 200 ❌ |
| net_r (governed) | −10.15 | — |
| net_r_3x | −10.71 | > 0 ❌ |
| max_dd_r (per-window) | −16.24 | ≤ 11.65 ❌ |
| deflated CI (α/12) | [−16.04, +1.22] | lower > 0 ❌ |
| fitted governor | target_vol=0.015, size_max=1.0, dd_budget=11.65 | — |
| train segment | 266 trades | — |

Gate 1 fails on all four criteria. The best-fit **conservative** governor (lowest vol
target, least leverage) is still net-negative at 3× cost with a CI that straddles 0.

## Honest read

The horizon-exit + portfolio governor did **not** harvest the known drift under the
drawdown cap on validation. The structural wall held — consistent with the full program
history ([[funding-probe-results]], [[profit-maximization-phases]]).

**But this is an UNDERPOWERED negative, and the run exposed two instrument defects that make
the DD-cap test specifically unreliable.** These are recorded, not re-run (stop rule: one
registered run, no re-tuning on this data):

1. **Validation n collapsed 266→8.** `govern()` maintains a *global* cumulative-drawdown
   state across the whole 2020→2026 series and drops size-0 trades. The strategy was
   persistently underwater entering validation, so the throttle pinned exposure near zero
   and ~92% of would-be validation trades were dropped. n=8 is far below any power floor —
   the validation sample is not a fair test of the hypothesis, it is mostly "the governor
   already switched itself off."
2. **Per-window vs global DD mismatch.** The throttle bounds the *global* governed
   drawdown to ~`dd_budget`, but the gate measures *per-window* maxDD (each window's equity
   curve resets to 0). So maxDD −16.24 exceeding budget −11.65 is not a governor failure —
   it is an apples-to-oranges comparison baked into the harness. The DD-cap gate is not
   actually testing the quantity the throttle controls.

## What is and isn't concluded

- **Concluded:** Slice-1 as-built does NOT break the wall; even a conservative best-fit
  governor is net-negative at 3× cost OOS. The sealed year stays unspent.
- **NOT concluded:** the "harvest the known drift" thesis is not *cleanly* falsified at
  power, because the two instrument defects above degraded the validation test. A corrected
  instrument (global governed-curve DD metric; throttle that does not silently collapse the
  evaluated sample — e.g. evaluate on the ungoverned entry stream and report the governed
  overlay separately) would be a **new registration**, with the sealed year still available.

## Decision pending (human)

Either (a) accept this as a negative and move to a genuinely different hypothesis (sealed
year preserved), or (b) treat Slice-1 v1 as a flawed instrument, fix the two defects, and
re-register as Slice-1b. Recommendation: (b) is cheap and the defects are real, but the
robust net-negative signal means expectations should stay low.
