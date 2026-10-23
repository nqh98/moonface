# Confluence engine — live-faithful honest re-evaluation (2026-06-25)

**Label: engine paper — disciplined heuristic, no validated-edge claim.**
This run does not rescue the engine or claim an edge. Its sole purpose is to
produce a **reproducible, live-faithful verdict from committed code** that
corrects the framing of the "+71.3R" headline recorded in
`FORWARD_FAITHFUL_BACKTEST_2026-06-24.md` (which was verified with throwaway
`/tmp` harnesses, not the committed tool). **Engine status is unchanged:
paper / WAIT, no validated edge. No forward watch started.**

## What changed since the +71.3R note

The committed backtest tool was **not** live-faithful: `tools/engine_backtest.replay`
fed `evaluate_engine` the full expanding history (`candles[:j+1]`), the path the
2026-06-24 doc itself flagged as overstating (the expanding `vol_ratio` baseline
live never has). Live feeds exactly `cfg.lookback_bars` (1500) candles per tick.

- **Fix:** commit `5370d41` — `replay` now feeds `candles[max(0, j+1-lookback_bars) : j+1]`,
  with a regression test (`test_replay_feeds_at_most_lookback_bars`) asserting the
  replay never feeds more than `lookback_bars` candles.
- **Reproducible verdict tool:** `tools/engine_honest_report.py` (pure
  `build_report` + thin CLI) drives that faithful `replay` and emits the
  committed scorecard plus three framing-correction blocks
  (`src/moonface/signal/engine/honesty.py`: recency, outlier dependence, cost
  sensitivity). This supersedes the `/tmp` harnesses.

## Data (verified, fingerprinted)

- `BTC/USDT:USDT` 1h (Binance USDT perp), 2020-01-01 → 2026-06-24, **56,800 bars, 6.484 y**.
- `sha256(.backtest_cache/BTC_USDT:USDT_1h.csv)` =
  `b1da38622859ca3937fe92bab12f7f6e7448099dfeb2d5da6fc4df1bcaeea2da` (same file as the 2026-06-24 run).
- Engine config `promotion/engine.json` (layered kill-switch), `engine_version` `6961993e71d5…`.

## Reproduce (committed code only)

```
.venv/bin/python -m tools.engine_honest_report \
    --engine promotion/engine.json \
    --start-ms 1577836800000 --end-ms 1782316800000 \
    --out /tmp/engine_honest_report.json
```

## Result — the +71.3R reproduces, and so does its disqualification

| core scorecard | value |
|---|---|
| closed trades | 235 |
| net R | **+71.29R** |
| expectancy | +0.30R / trade |
| profit factor | 1.29 |
| win rate | 34.9% |
| max drawdown (R) | **−30.03R** |
| state / pause_reason | **paused / hard_breaker** |

The live-faithful committed tool reproduces the +71.29R / 235-trade number
**exactly**. So the figure is genuine and now reproducible — but the same report
shows it is **not deployment-grade**, on three counts:

### 1. It is a frozen 2020–2022 sample — the recent years are unobserved

| recency segment | trades | net R |
|---|---|---|
| full | 235 | +71.29 |
| **first_half** | **235** | **+71.29** |
| **second_half** | **0** | **0.0** |
| **last_365d** | **0** | **0.0** |

Every trade falls in the first half of the window. The engine bled to the
**−30R hard breaker**, latched (`pause_reason: hard_breaker`), and emitted WAIT
for the entire second half and the last 365 days. The layered kill-switch did
**not** fix the freeze the all-time latch caused — it moved the latch from −15R
to −30R. **2023 → 2026 is still unobserved by the shipped config.**

### 2. The net result is carried by ~3 trades

| outlier metric | value |
|---|---|
| best trade R | **+48.09** |
| net R ex-best-1 | +23.20 |
| **net R ex-best-3** | **−14.88** |
| net R ex-best-5 | −41.07 |
| best-1 share of gross profit | 15.4% |
| top-3 share of gross profit | 27.5% |

Removing the top three trades makes the result **net-negative**. The "+71.29R"
is a handful of 2020–2021 trend captures, not a population edge. ("15% outlier
dependence" in the prior note is the *single* best trade's share of gross
profit — it understates the dependence that `net_r_ex_best3 = −14.88R` exposes.)

### 3. Thin and cost-fragile

| cost (fee + slippage) | net R |
|---|---|
| 1× (10 bps round-trip) | +71.29 |
| 2× | +46.36 |
| 3× | +21.44 |
| 5× | **−28.42** |

PF 1.29 at 1× is breakeven-grade for trend following, and the edge is gone by
5× cost. The base 10 bps round-trip is already thin for fee + slippage on a 1h
perp (Binance taker alone ≈ 8 bps round-trip), so the realistic margin is
nearer the 2–3× column.

## Verdict

- **The +71.3R headline is reproducible from committed code, and is corrected,
  not rescued:** it describes a frozen 2020–2022 window carried by three trades,
  thin and cost-fragile, with the recent three-plus years unobserved because the
  engine is hard-latched. There is no validated edge.
- **No configuration satisfies both constraints at once.** The only run that
  *observes* the recent years (trailing-window only, no hard breaker, 2026-06-24
  exploratory) reached −55.9R cumulative drawdown (3.7× budget) — unacceptable.
  Within the −30R budget the engine freezes before the deployment period.
- **The engine's backtest mechanics are sound** (audited 2026-06-25): no intrabar
  exit look-ahead (`position.py` checks the prior-bar stop before ratcheting), no
  partial-bar regime look-ahead (`resample.py` drops incomplete 4h groups), cost
  nets fee + slippage in R. The problem was never look-ahead; it is that there is
  no edge.

**Engine status: paper / WAIT, no validated edge. No forward watch. A real
improvement requires a different signal hypothesis, not re-tuning this one.**
