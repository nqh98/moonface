# BTC Practical FULL Re-Evaluation — Findings (2026-06-25)

**Verdict: NEGATIVE — no forward-paper-watch candidate.** DSR was *reported, never
gated*; the practical bar (net-positive after fees, |DD|<=30R, >=30 trades, not
outlier-dependent, robust to **2x/3x** cost, active recently, dual holdout
replication) decided every outcome.

## What this run is

The first run to push **all 11 sweepable BTC price families** (old families +
the requested new mechanisms: context-filtered / WAIT-heavy `vol_regime`,
`trend_pullback`, vol-breakout cores `vol_compression_breakout` / `vol_expansion`
/ donchian / atr_channel, classic trend, mean-revert) x family-matched exits
(incl. alternative trend exits `atr_trail` / `chandelier`) through **one**
practical harness over the full **6.5y** window (2h+4h), with a clean
train->holdout split and the user's stricter 2x/3x multiplicative cost gate.

- Grid: 132 configs. Split (4h): Explore/train **2020-01 -> 2023-11**, Validate
  **2023-11 -> 2025-03**, Sealed/holdout (most-recent) **2025-03 -> 2026-06**.
- Selection (train slice): **3 of 132** cleared the *entire* battery including the
  2x and 3x cost gate — already more than the prior practical lane (0 survivors).

## The 3 finalists and why they were rejected

All 4h / `atr_trail`. Per-segment net-R (costs in):

| family (4h, atr_trail) | train PF / exp | validate PF / exp | **sealed (recent) PF / exp** | 2x/3x cost (val) | 2x/3x cost (sealed) |
|---|---|---|---|---|---|
| donchian_break n=100 | 2.28 / +0.93 (n80) | 1.41 / +0.37 (n29) | **0.64 / -0.33 (n32)** | pass / pass | fail / fail |
| atr_channel_break k=2.0 | 2.06 / +0.63 (n78) | 1.43 / +0.35 (n28) | **0.87 / -0.11 (n27)** | pass / pass | fail / fail |
| vol_expansion mult=3.0 | 1.97 / +0.61 (n140) | 1.92 / +0.56 (n47) | **0.57 / -0.32 (n32)** | pass / pass | fail / fail |

They are **net-positive, drawdown-acceptable, outlier-clean, and robust to 3x
cost through 2025** — then reverse to negative expectancy in the most-recent ~15
months (adequate samples, 27-32 sealed trades — not a small-sample fluke). The
killer is **recency / OOS sign-reversal**, not DSR, not cost, not drawdown,
not outliers. BTC 4h trend/breakout edge that held 2020-2024 has decayed in the
2025-26 regime.

## Direct answer to "were old strategies rejected only by DSR?"

**No.** When the same families are judged by the practical bar (this run + the
prior btcspec/playbook/practical lanes), they fail for **practical** reasons —
recent decay, >30R drawdown, outlier-dependence, or OOS sign-reversal. The
single closest historical near-miss (btcspec `2h donchian_break+donchian_trail`,
sealed PF 1.60) was **outlier-dependent** (+57R single trade) and would fail this
lane's outlier gate. Dropping DSR did not rescue any family.

## Status / isolation

PAPER-only research. Donchian Slice-3 / promotion / live journal untouched;
`EXIT_REGISTRY` unchanged. The existing 4h Donchian remains the program's only
active-paper item (unchanged by this lane). No promotion, no paper-watch start.
Reproduce: `python -m tools.btc_practical_full --explore|--select|--validate
--start-ms 1577836800000 --end-ms 1782000000000 --out-dir experiments/practical_full`.
