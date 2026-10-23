# BTC 4h Donchian — recency-by-year audit (2026-06-25)

**Purpose.** The revalidation report (`DONCHIAN_REVALIDATION_RESULT.md`) reports
aggregate walk-forward and cost stress but does **not** break the deployed
config out by calendar year. The acceptance bar requires "not dead or inactive
in the most recent period." This addendum supplies that evidence, reproducibly,
for the byte-identical deployed config. It does **not** change the verdict or
any frozen registration threshold.

## Config under test (deployed, byte-identical)
- `donchian_break entry_n=40`, exit `donchian_trail trail_n=20, k_stop=2.0,
  atr_period=14`, long+short per `_BASE`, fraction handled by sim.
- `BTCUSDT 4h`, 2020-01-01 → 2026-06-24, **14,175 bars**, costs netted in R.

## Reproduce (committed code only)
```
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,"src")
from dataclasses import replace
from datetime import datetime, timezone
from collections import defaultdict
from moonface.research.trend_sim import simulate_donchian
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from tools.swing_donchian import _BASE
c=fetch_perp_candles("BTCUSDT","4h",1577836800000,1782316800000,"cache/swing")
f=fetch_funding_rates("BTCUSDT",1577836800000,1782316800000,"cache/swing")
t=simulate_donchian(c, replace(_BASE,entry_n=40,trail_n=20), f)
by=defaultdict(lambda:[0,0.0])
for x in t:
    y=datetime.fromtimestamp(c[x.exit_index].timestamp_ms/1000,tz=timezone.utc).year
    by[y][0]+=1; by[y][1]+=x.r_multiple
for y in sorted(by): print(y, by[y])
PY
```

## Result

| exit year | trades | net R | cumulative R |
|---|---|---|---|
| 2020 | 22 | **+39.43** | +39.43 |
| 2021 | 22 | +3.88 | +43.31 |
| 2022 | 17 | −5.38 | +37.93 |
| 2023 | 18 | **+44.63** | +82.56 |
| 2024 | 22 | +13.64 | +96.20 |
| 2025 | 20 | −1.54 | +94.66 |
| 2026 (YTD) | 12 | −8.65 | +86.00 |
| **TOTAL** | **133** | **+86.00** | |
| **trailing 365d** | **24** | **−11.76** | |

(The +86R full-window simulate differs from the walk-forward framing in the
revalidation report, which splits the path into N=4 non-overlapping windows; this
is the raw single-pass equity, not a pass/fail gate.)

## Reading — the good and the bad, honestly

**Not frozen (passes the activity test).** Unlike the confluence engine — which
latched its all-time drawdown breaker in 2022 and did **0 trades** in the
second half of its window — the Donchian fires **~20 trades every year**,
including the most recent 12 months. It is alive and would be placing signals
forward. This is its single most important advantage over every other artifact
in the program.

**Not single-outlier dependent across time.** The profit is earned in two
distinct, well-separated regimes — 2020 (+39R, the 2020-21 bull) and 2023
(+45R, the post-FTX recovery trend) — plus a solid 2024 (+14R). It is not a
single-year fluke. (This is consistent with the revalidation's `exp_drop_top1 =
+0.43R` — dropping the single best trade leaves expectancy clearly positive.)

**But it is underwater in the recent period.** 2025 was roughly flat (−1.54R),
2026 YTD is negative (−8.65R), and the **trailing 365 days are net −11.76R**.
The strategy is in a real, ~18-month chop drawdown right now. That magnitude is
inside a trend-follower's normal envelope (revalidation maxDD −15R at base
cost), so it is **not** a kill signal — but it does mean the deployed config is
**not currently demonstrating its edge out of sample.**

## Bearing on the verdict

This is exactly why the correct status is **INCONCLUSIVE / paper**, resolved by
the frozen forward registration (`DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`), not
promotion:
- It clears activity, cost-robustness, drawdown control, and cross-regime
  outlier checks.
- It does **not** clear "currently profitable in the recent period" — the live
  evidence the forward paper journal is accumulating is the only honest way to
  resolve whether the 2025-26 drawdown is mean-reverting trend-follower noise or
  regime decay.
- The forward registration's early-DD-kill is the guard against the latter.

**No live promotion. Keep on paper. Watch the forward journal against the frozen
criteria.**
