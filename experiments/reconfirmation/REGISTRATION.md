# Multi-Timeframe Reconfirmation Program — Registration v1

- **Registered:** 2026-06-12 (before first data look)
- **Purpose:** standing quarterly reconfirmation behind
  `promotion/participation.json` `reconfirm_by`. Reconfirmation, not search.
- **Authority:** report-only. The tool never writes `promotion/`.
- **Design spec:** docs/research-log/specs/2026-06-12-multi-timeframe-reconfirmation-design.md (untracked docs/)

## Frozen measurement (identical on every timeframe)

- Asset: binance `BTC/USDT:USDT`; timeframes `1h`, `4h`, `1d`, `1w`.
- Window: rolling 3 years (1095 days) ending at the last closed bar.
- Entries: `donchian_break {"n": 100}`, LONG side only (the advisor never shorts).
- Scoring: `single_trade_r(..., "horizon_hold", {"n_bars": 24, "atr_period": 14})`,
  net of `COST_FRACTION = 0.001`. Overlapping events allowed (probe convention).
- Folds: research = first 80% of bars, OOS = last 20%, events assigned by
  entry index. Events with `i + 24 > len(candles) - 1` are excluded.

## Pre-registered verdicts (per timeframe, in order)

1. `INSUFFICIENT` — total events < 30, or OOS events < 10.
2. `ALIVE` — research-fold mean net R > 0 AND OOS-fold mean net R > 0.
3. `DEGRADED` — otherwise.

4h-only flag, independent of verdict: `ANCHOR BREACHED` when the unstopped
cumulative-R max drawdown over the window exceeds 277R
(`WORST_OBSERVED_DRAWDOWN_R`): the policy loader's sizing inequality then
understates observed risk.

Descriptive only, never part of a verdict: the "since last run" slice
(events after the previous run's last bar, from the prior `results.json`).

## Pre-stated expectations (so outcomes cannot be reinterpreted)

4h answers the real question (ALIVE or DEGRADED). 1h has the largest n.
1d is borderline-INSUFFICIENT. 1w is INSUFFICIENT almost surely (~157 bars
minus the 100-bar warmup). INSUFFICIENT is a permanent, useful verdict: it
documents why the advisor cannot extend to that timeframe.

## Pre-committed human actions

| Outcome | Action |
|---|---|
| 4h ALIVE, anchor intact | bump `reconfirm_by` one quarter |
| 4h DEGRADED or INSUFFICIENT | review; default: let `reconfirm_by` lapse, or set `enabled: false` |
| ANCHOR BREACHED | resize `risk_fraction`/`max_account_drawdown` or disable |
| 1h/1d/1w anything | informational; timeframe extension requires a new pre-registered promotion study |

## Change policy

Any alteration of parameters, verdict rules, or timeframes is a new
registration version (v2, ...) committed before data is looked at. Failed
or degraded verdicts are never retried with variations.
