# Signal Matrix — Slice-1b Registered Run Results

**Date:** 2026-07-07
**Verdict:** `CLOSED_NEGATIVE_VALIDATION` (clean, well-powered)
**Report:** `experiments/engine/matrix_slice1b_2026-07.json`
**Registration:** `experiments/engine/MATRIX_SLICE1B_REGISTRATION.md` (frozen, pre-run)
**Sealed BTC year:** **NOT opened** (Gate 1 failed → gate2/gate3 null). Bullet intact.

## Result (corrected instrument)

| metric | Slice-1 (flawed) | Slice-1b (corrected) | gate |
|---|---|---|---|
| validation n | 8 | **106** | ≥ 40 ✅ |
| net_r (governed) | −10.15 | −1.82 | — |
| net_r_3x | −10.71 | −3.08 | > 0 ❌ |
| deflated CI (α/12) | [−16.04, +1.22] | **[−0.86, +0.73]** | lower > 0 ❌ |
| max_dd_r | −16.24 | −22.17 | ≤ 11.65 ❌ |
| fitted governor | tv=0.015, sm=1.0 | tv=0.015, sm=1.0 | — |

The three Slice-1 defects are fixed: n recovered 8→106 (per-segment reset + retained zeros +
recalibrated floor), and the DD frame is now per-segment throughout.

## Decisive finding

**At real power (n=106), the governed horizon-harvest strategy's mean-R CI is
[−0.86, +0.73] — tightly centered on zero — and net-negative at 3× cost.** The known drift
(`funding_fade` +0.82R/trade horizon; Donchian +74.79R) does **not** survive the round-trip
into a bounded, cost-real, volatility-sized strategy. This is a clean, well-powered NO.

This **falsifies the "harvest the known drift" thesis** the whole matrix was built to test:
matching the exit to the drift horizon and bounding risk with a portfolio governor — the two
levers no prior experiment varied — does not convert the replicated drift into edge. The
program's structural wall stands, now confirmed with the exit+governor levers explicitly
exercised and failed (deeper than "the bracket was wrong"). Consistent with
[[profit-maximization-phases]] and the [[funding-probe-results]] wall.

## Secondary finding (governor mechanism limitation)

maxDD −22.17 breaches the −11.65 budget **even with per-segment DD reset**. The linear
drawdown throttle (`g_t = clip((budget − dd_before)/budget, 0, 1)`) is reactive: a cluster of
losses accumulates past the budget before `g_t` clamps toward zero. So "de-lever toward the
cap" **slows** drawdown but does **not hard-enforce** it — overshoot ≈ 2× here. Moot for this
verdict (no positive edge to protect), but a real limitation of the mechanism for any future
use.

## Stop rule → executed

Per the pre-committed rule (`MATRIX_SLICE1B_REGISTRATION.md`), CLOSED_NEGATIVE on the
corrected instrument **closes Slices 2–3** (meta-labeled conviction; multi-asset netting):
the base governed stream has no net-R to select from (CI centered on zero), so a conviction
gate has nothing to gate. The signal-matrix horizon-harvest lane is **CLOSED NEGATIVE**.
Sealed BTC year preserved (unspent) for a genuinely different future hypothesis / new data.
