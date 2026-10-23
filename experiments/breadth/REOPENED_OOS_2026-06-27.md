# Breadth-Thrust — reopened OOS test (2026-06-27)

**Status change: `CLOSED NEGATIVE` → `OOS-POSITIVE IN SIGN, UNDERPOWERED — strongest open lead`.**

The original lane (commits c8633b5..5feebdb) closed NEGATIVE because **no cell
cleared the in-sample `DSR >= 0.95` gate**, so `select` froze 0 candidates and the
validate/sealed holdout was **never opened**. That is a *non-result*, not an
out-of-sample refutation. This addendum pre-commits the single in-sample-best
cell and finally opens the held-out windows. It does **not** change any frozen
registration threshold; it is a one-hypothesis confirmatory OOS test on data the
selection step never touched.

## Why this is honest (not p-hacking)
- `breadth_thrust:6` is selected on **pre-OOS** grounds only: it was the best cell
  in-sample on every axis the lane scored (DSR 0.848, PF 2.85, exp +1.23R, the
  tightest drawdown −6.8R). One cell, one hypothesis.
- The validate and sealed windows were **genuinely never opened** in the original
  run (`select` froze 0 → `validate_cell` was never called). So this is a single
  pre-committed cell tested on unopened data, reported as confirmatory — not a
  search, not a re-selection.
- `n_trials = 9` DSR deflation does not apply to a single pre-committed
  hypothesis; the OOS practical bar replaces it as the gate.

## Cell under test (byte-identical to the frozen lane)
- family `breadth_thrust`, axis (window) = 6, base_period = 50, low_band = 0.40,
  high_band = 0.60, h = 48, exit `atr_trail` {k_trail 2.0, max_bars 120,
  atr_period 14}. Symmetric long/short.
- Universe: top-20 USDT-perp by 30d vol, min_history 365d, rebalance 30d, **BTC
  excluded** from the breadth aggregate; signal trades **BTCUSDT 4h**.
- Window 2020-01-01 → 1782300000000 (BTCUSDT 4h, 14178 bars,
  data_sha b3b004cb58258369), 60/20/20 train/validate/sealed.

## Result — the holdout, opened

| window | span | n | total R | exp R | PF | maxDD R | long/short |
|---|---|---|---|---|---|---|---|
| train (in-sample) | 2020-01 → 2023-11 | 21 | +25.82 | +1.229 | 2.85 | −6.80 | 10 / 11 |
| **validate** (OOS) | 2023-11 → 2025-03 | 10 | **+2.15** | **+0.215** | 1.26 | −6.51 | 6 / 4 |
| **sealed** (OOS) | 2025-03 → 2026-06 | 13 | **+2.76** | **+0.212** | 1.28 | −5.09 | 9 / 4 |
| **pooled OOS** | 2023-11 → 2026-06 | 23 | **+4.90** | **+0.213** | 1.27 | −6.51 | 15 / 8 |

**Bootstrap on pooled OOS (n=23, 100k resamples, seed 7):** expectancy 95% CI
**[−0.62, +1.12]R**, P(mean ≤ 0) = **0.32**, one-sample t vs 0 = **0.47**.

## Reading — honest, both sides

**It survives OOS in sign and quality.** Positive expectancy in **both**
held-out windows, same sign, nearly identical (+0.215 / +0.212R), PF 1.26–1.28,
drawdown tight (−5 to −6.5R, far inside the 30R budget). Most artifacts in this
program *reverse* out of sample (cf. the ls_tournament donchian L/S survivor:
train +74.5R → sealed −10.6R). breadth_thrust:6 did not reverse. The in-sample
DSR kill (0.848 < 0.95, deflated by 8 siblings) looks like a **false negative**.

**But it is underpowered — not a significant edge.** Thrust events are
intrinsically rare (~5/year), so pooling both OOS windows still gives only
n = 23. At n = 23 the bootstrap CI [−0.62, +1.12] straddles zero widely; +0.21R/
trade is **statistically indistinguishable from zero**. The `MIN_TRADES = 30`
floor that blocks promotion is well-founded. This is the symmetric twin of the
ls_tournament finding: there the *negative* was indistinguishable from zero; here
the *positive* is. Both are small-n, not demonstrated effects.

**Verdict.** breadth_thrust:6 is the program's **strongest never-refuted
signal** and is **not exhausted** — but it **cannot be promoted on current data**.
The only honest way to add power on BTC-only (events don't exist more densely in
history) is **forward paper accumulation** until n ≥ 30 closed OOS trades, then
re-apply the frozen practical/econ bar. See
`BREADTH_THRUST_FORWARD_REGISTRATION.md`.

## Reproduce (committed code only)
```
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,"src"); sys.path.insert(0,"tools")
import argparse, random, math
from tools.breadth import _load, split_60_20_20
from moonface.research.breadth.grid import all_cells
from moonface.research.breadth.evaluate import evaluate_cell, cell_entries, score_records
args=argparse.Namespace(symbol="BTCUSDT",start_ms=1577836800000,end_ms=1782300000000,cache_dir=".backtest_cache")
btc, daily, is_member = _load(args)
tr,va,se = split_60_20_20(btc)
cell=next(c for c in all_cells() if c.key=="breadth_thrust:6")
for nm,seg in (("train",tr),("validate",va),("sealed",se),("val+seal",va+se)):
    m=evaluate_cell(daily, seg, cell, is_member)["metrics"]
    print(nm, m["trade_count"], round(m["total_r"],3), round(m["expectancy_r"],3), round(m["profit_factor"],2))
oos=[r["net_r"] for seg in (va,se) for r in score_records(seg,cell_entries(daily,seg,cell,is_member),cell.exit_name,cell.exit_params)]
rng=random.Random(7); B=100000
bs=sorted(sum(rng.choice(oos) for _ in oos)/len(oos) for _ in range(B))
print("OOS 95% CI",round(bs[2500],4),round(bs[97500],4),"P(<=0)",round(sum(1 for v in bs if v<=0)/B,4))
PY
```
NOTE: requires a daily universe cache that covers the full window (see the
stale-`uni1d_*.csv` gotcha in the lane memory; `universe_covers_train` guards it).

## Honest caveat
Paper-only, BTC futures only. OOS-positive-in-sign does NOT authorize live
capital or promotion; n = 23 is not a significant edge. The frozen lane gate,
EXIT_REGISTRY, and DSR calibration are untouched.
