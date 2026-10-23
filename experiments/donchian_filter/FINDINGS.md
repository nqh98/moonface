# Donchian ADX-Filter Lane — Findings (2026-06-26)

**Verdict: NEGATIVE (honest economic read), despite a frozen-rule `IMPROVES` label.**
Paper-only. Donchian stays on paper unchanged. The ADX gate is NOT added to the
Slice-3 forward registration.

## What was tested

Gate the byte-frozen BTC 4h Donchian 40/20 entries on `ADX(14) >= threshold`
(subset of base trades; `simulate_donchian` untouched). Single mechanism, 3
thresholds {18, 20, 25}, selected on train only, sealed 2025-03 → 2026-06 opened
once. Design: `docs/research-log/specs/2026-06-26-donchian-adx-filter-design.md`.
Code: `src/moonface/research/donchian_filter/`, `tools/donchian_filter.py`
(merged c9384d9). 20/20 lane tests green.

## Selection (train, clean)

ADX>=20 frozen — qualified outright: train net 67.66R (90.5% of base 74.79R),
maxDD -5.50R (vs base -8.77R), robust_frac 0.9167 (vs 0.8333), n=51 (>= floor).
ADX>=18 failed 90% trend-capture; ADX>=25 gutted activity + robustness.

## Sealed holdout 2025-03 → 2026-06

| metric | base 40/20 | ADX>=20 gated |
|---|---|---|
| net R | -10.24 | -9.79 |
| max DD R | -14.75 | -11.01 |
| trades | 30 | 17 |
| expectancy/trade | -0.34 | -0.58 |
| profit factor | 0.48 | 0.25 |

Frozen verdict rule = `IMPROVES` (gated maxDD less negative AND gated net_r >
base net_r). **This label is economically misleading and is corrected here.**

## Honest interpretation — the gate targets the wrong trades

- **Still net-negative** (-9.79R over 15 months). The "improvement" is **+0.45R** —
  noise inside a trend-follower's normal envelope.
- The **13 trades the filter removed** collectively netted only **-0.45R** (~breakeven
  low-ADX chop). They were not the source of the drawdown.
- The **17 trades it kept** (high-ADX) net **-9.79R**, with **worse** per-trade
  expectancy (-0.58 vs -0.34) and **worse** PF (0.25 vs 0.48) than base.
- Therefore the 2025-2026 bleed is **not** low-ADX chop — it is **high-ADX breakout
  failures** (breakouts that triggered *with* trend strength, then reversed). A
  trend-strength gate cannot fix a drawdown whose losing trades have trend strength.

The hypothesis ("ADX trend-strength gating reduces the chop drawdown without
destroying trend capture") is **falsified**: the gate reduces total loss only by
sitting out near-breakeven trades, while concentrating into worse-quality retained
trades. No edge is rescued.

## Bearing on the program

Consistent with the structural-drawdown wall. The lane discipline worked: train
selection was clean, the sealed window was opened once, and the frozen label is
reported AND honestly corrected (not rescued). Status unchanged — Donchian remains
the only active-paper item, resolved forward by
`experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`. No promotion, no
re-tuning, no second lever.

## Reproduce

```
.venv/bin/python -m tools.donchian_filter --register --out-dir experiments/donchian_filter
.venv/bin/python -m tools.donchian_filter --explore  --out-dir experiments/donchian_filter
.venv/bin/python -m tools.donchian_filter --select   --out-dir experiments/donchian_filter
.venv/bin/python -m tools.donchian_filter --validate --out-dir experiments/donchian_filter
```
