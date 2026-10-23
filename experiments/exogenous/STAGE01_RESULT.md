# Exogenous-Conditioned BTC State Model — Stage 0 + Stage 1 First Run

**Date:** 2026-06-26
**Window:** start_ms 1577836800000 (2020-01-01) → end_ms 1782300000000 (~2026-06-23)
**Commands:**
```
.venv/bin/python -m tools.exogenous_btc --readiness --cache-dir cache/exogenous --out-dir experiments/exogenous
.venv/bin/python -m tools.exogenous_btc --screen --start-ms 1577836800000 --end-ms 1782300000000
```
**Status:** Stage 0 PASSED. Stage 1 **PASSED** (`screen_passes: true`) — the lane does NOT close at Stage 1.

---

## Stage 0 — Newdata readiness (all `ready`)

| source | status | history_days |
|--------|--------|--------------|
| FRED:SP500 | ready | 3650 |
| FRED:DTWEXBGS | ready | 7472 |
| FRED:VIXCLS | ready | 13322 |
| FRED:DGS2 | ready | 18285 |
| FRED:DGS10 | ready | 23549 |
| Deribit:DVOL | ready | 499 |

All six sources clear the `assess_manifest` gate (fields, coverage, monotonicity, license).

**Note (DVOL):** DVOL reports `history_days: 499` (~1.4y) despite Deribit DVOL existing since
late 2020. This looks like early pagination termination in `fetch_dvol` (the
no-forward-progress guard `if last < cursor + resolution: break` can fire when a page's
last bar is short of a full resolution step). It clears the 180-day MIN_HISTORY_DAYS floor, so
readiness passes. DVOL is only the *reserved* dvol-premium derived state and is **not screened
in v1**, so this truncation does not affect the Stage-1 result. Worth a follow-up to extend the
DVOL fetch before any v1.1 that screens the derived state.

---

## Stage 1 — Gross conditional-drift screen (frozen `|t| >= 2.0`)

Newey-West HAC t-statistic of sign-scaled BTC daily returns, conditional on each state active:

| state | t | n | mean | sign | clears `|t|>=2.0`? |
|-------|------|------|---------|------|--------------------|
| `equity_riskon` (SP500 20d%>0, long) | **2.5089** | 1586 | +0.001779 | +1 | **YES** |
| `dollar_weak` (DTWEXBGS 20d%<0, long) | 1.753 | 1188 | +0.001481 | +1 | no |
| `vix_low` (VIXCLS<20, long) | 0.13 | 1343 | +0.000092 | +1 | no |
| `vix_high` (VIXCLS>30, short) | -0.5776 | 210 | -0.001606 | -1 | no |

`screen_passes` = **true** (one state, `equity_riskon`, clears 2.0).

---

## Honest reading (one paragraph)

**This is an unexpected result against the pre-registration**, which predicted a Stage-1
NEGATIVE kill (consistent with the program's structural-drawdown findings across every prior
lane). Instead, BTC long exposure conditional on SP500 being up over the prior 20 trading days
shows a gross (pre-cost) conditional drift of **t = 2.51** over 1586 active bars (mean +0.178%
per bar). This clears the frozen Stage-1 `|t| >= 2.0` gate, so the lane proceeds rather than
closing. Three caveats temper this before any celebration: (1) it is a **gross, pre-cost** stat
— the vol-normalized episode backtest (`run_backtest`) with round-trip costs and the Stage-3
economic bar have not yet been applied; (2) it is a **single family** (equity risk-on) out of
four screened, and the others are weak (`dollar_weak` t=1.75 close but under; `vix_low`/`vix_high`
null), so this is one signal, not a robust set; (3) it has not survived the Stage-2 DSR
deflation (n_trials=6) or the Stage-4 ETH/SOL transfer gate, either of which can still kill it.
The economically intuitive sign (equity risk-on → long BTC, +1) is correct and the effect is in
the expected direction — but a t=2.51 gross drift is exactly the magnitude that DSR deflation
and transaction costs are designed to erode. Per the pre-registered staged gate, the honest next
step is `--validate` (Stage-2 DSR + Stage-3 walk-forward econ bar) on the `equity_riskon`
survivor — NOT a conclusion that an edge exists.

---

## Next (pre-registered, human-gated)

Per the plan, subsequent stages run in later human-gated sessions:
1. `--explore` / `--select` (freeze `equity_riskon` as the survivor into `frozen_candidates.json`, commit).
2. `--validate` (Stage-2 DSR ≥ 0.95 pooled over n_trials=6, AND Stage-3 walk-forward econ bar).
3. `--transfer` (Stage-4 ETH/SOL all-pass) — only if validate passes.
4. `--forward` (Stage-5) — only if a survivor reaches paper registration.

The kill rule remains: fail ANY subsequent stage ⇒ CLOSED NEGATIVE, no v2.
