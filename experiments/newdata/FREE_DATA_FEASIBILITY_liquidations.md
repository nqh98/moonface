# Free-Data Feasibility — Binance USD-M liquidations (Lane 3 / Setup 3)

**Date:** 2026-07-08
**Scope:** Can free liquidation data serve Setup 3 (Liquidation Absorption)?
Answers the standard seven questions. No backtest is staged; no lockbox exists.

## Bottom line
- **Q1 source:** Binance USD-M `!forceOrder@arr` WebSocket (per-symbol
  `BTCUSDT@forceOrder`), keyless. Collected via `ccxt.pro` `watch_liquidations`
  (`tools/liquidation_collect.py`).
- **Q2 schema:** side, price, qty, timestamp → normalized
  `{ts_ms, symbol, side, price, qty, notional}` (`liquidation_feed.CSV_FIELDS`).
- **Q3 history:** **NONE.** There is no free historical liquidation archive
  (Binance Vision does not publish liquidations). Forward-collection only.
- **Q4 reproducible:** No — a live stream; whatever is not captured is lost.
- **Q5 access cost:** Trivial (keyless WS), but requires an always-on collector.
- **Q6 genuinely new:** YES in principle — realized forced-exit prints are not
  derivable from OHLCV/OI/funding the repo already holds. BUT see the throttle.
- **Q7 decision:** FORWARD-COLLECT now (Track B collector shipped); Setup 3
  pre-registration DEFERRED behind the readiness gate below.

## The throttle (critical caveat)
Binance rate-limits `forceOrder` to **1 order/sec/symbol** (since 2021-04).
During a cascade — the exact event Setup 3 targets — the feed emits a *sample*,
not the true tape. Cascade *timing/direction* is faithful; cascade *magnitude*
is systematically undercounted. Any Setup 3 feature must be robust to this
(e.g. use cluster presence/direction, not summed notional as ground truth).

## CVD-proxy dependency
Setup 3's confirmation term ("liqs fire but price stalls and CVD drops =
absorption") needs signed flow, and signed CVD is dead on free data
([[aggtrades-hawkes-results]], 2026-07-03). Setup 3 will therefore substitute an
OHLCV-derived absorption proxy (e.g. price-stall + range-compression after a
cluster), NOT signed CVD. This is a known weakness recorded before any test.

## Readiness gate (Setup 3 pre-registration blocked until ALL met)
1. `>= 180` calendar days of continuous collection (`history_days`), AND
2. `>= 200` distinct cascade clusters (`cascade_clusters`, 60s grouping), AND
3. collector uptime coverage `>= 0.90` of days in the span (`coverage_ratio`).

Check with `.venv/bin/python tools/liquidation_collect.py --out
experiments/newdata/liquidations status`. Only then is a Setup 3 pre-registration
written — as a NEW experiment directory. **Cron is human ops** (same stance as the
Deribit chain collector):

```
* * * * * pgrep -f liquidation_collect || (cd <repo> && \
    .venv/bin/python tools/liquidation_collect.py --out \
    experiments/newdata/liquidations collect >> watch.log 2>&1 &)
```

## Relationship to prior lanes
Consistent with the Deribit chain collector (forward-collect, human-gated
readiness ~months out) and the aggressor-trades kill (signed CVD dead on free
data). This memo authorizes ONLY data acquisition; it makes no alpha claim and
opens no lockbox. Setup 3 remains DEFERRED.
