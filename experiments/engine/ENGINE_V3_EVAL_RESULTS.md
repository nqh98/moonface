# Engine v3 — Backtest Evaluation — RESULTS

**Run:** 2026-07-06, single registered run (`tools/v3_evaluate`).
**Pre-registration:** `ENGINE_V3_EVAL_2026-07.md` (FROZEN, hash `dccc879a…`).
**Report:** `experiments/engine/v3_eval_2026-07.json`.

## Verdict: `CLOSED_NEGATIVE_VALIDATION`

Gate 1 (BTC validation 2024-01 → 2025-07) failed. **The sealed 2025-07 →
2026-07 window and the ETH/SOL transfer test were never opened — the sealed
bullet is intact.**

## Gate 1 detail

| Criterion | Result | Pass |
|---|---|---|
| Power (n ≥ 200) | n = 301 | yes |
| Net-R @ 3× cost > 0 | **−62.88** (raw net-R +22.44) | no |
| Family-deflated block-CI lower > 0 (T=12) | **[−0.386, +0.590]** | no |
| Max-drawdown-R ≤ v2.2 | **−48.36** vs v2.2 **−11.65** | no |

Failed 3 of 4. The raw +22.44R is destroyed by realistic cost (301 trades,
thin per-trade edge), the mean-R bootstrap CI straddles zero (noise-
indistinguishable), and drawdown is ~4× the incumbent.

## Fitted candidate (train 2020-01 → 2024-01, n=4453 trades)

- **q_floors:** BREAKOUT 0.468, REVERSION 0.386, **PULLBACK 1.0 (vetoed —
  never non-negative train E[R])**.
- **Pruned cells → flat:** RANGING/QUIET, RANGING/HIGH (already flat),
  TRENDING_DOWN/NORMAL, TRENDING_DOWN/QUIET.
- **Surviving cells:** TRENDING_UP/{QUIET→PULLBACK*, NORMAL→BREAKOUT,
  HIGH→BREAKOUT}, TRENDING_DOWN/HIGH→BREAKOUT, RANGING/NORMAL→REVERSION.
  (*PULLBACK cell is effectively dead via q_floor 1.0.)

## Interpretation

Per spec §11's falsifiable bet: prior regime work failed because regime
*filtered an additive score*; here regime was a *selector* choosing one
specialist, with size-only scoring. It still fails — the negative falls on the
**selection architecture itself**, not on additive weighting. Cost-fragility +
drawdown + noise-level DSR reproduce the program's structural wall on a
genuinely new mechanism.

## Discipline

One registered run, as pre-registered. No re-tuning on this data (that would be
a new registration with its own deflation). The sealed year remains unused and
is available for a genuinely different future hypothesis. v2.2 stays the pinned
live engine; v3 is not promoted.
