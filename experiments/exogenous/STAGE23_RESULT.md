# Exogenous-Conditioned BTC State Model — Stage 2 + Stage 3 Result

**Date:** 2026-06-26
**Survivor frozen (Stage 1 → `--select`):** `equity_riskon` (SP500 20d%>0, long BTC), t=2.5089.
See `frozen_candidates.json` (n_trials=6).
**Command:**
```
.venv/bin/python -m tools.exogenous_btc --validate --start-ms 1577836800000 --end-ms 1782300000000
```
**Verdict: `passed: false` — lane CLOSED NEGATIVE at Stage 2 + Stage 3.**

---

## Result

```json
{
  "passed": false,
  "dsr_pass": false,
  "dsr": 0.0,
  "econ_passed": false,
  "metrics": {
    "expectancy_r": 1.2752,
    "profit_factor": 2.1022,
    "mar": 3.3428,
    "max_dd_r": -30.1378,
    "robust_frac": 0.75
  },
  "reasons": ["drawdown -30.1378R exceeds 30.0R tol"],
  "n_trials": 6
}
```

| Gate | Threshold | Observed | Pass? |
|------|-----------|----------|-------|
| Stage 2 — DSR | ≥ 0.95 (n_trials=6) | **0.0** | **FAIL** |
| Stage 3 — expectancy_r | ≥ 0.05 | 1.2752 | pass |
| Stage 3 — profit_factor | ≥ 1.2 | 2.1022 | pass |
| Stage 3 — MAR | ≥ 0.5 | 3.3428 | pass |
| Stage 3 — max_dd_r | ≥ -30.0 | **-30.1378** | **FAIL** (by 0.14R) |
| Stage 3 — robust_frac | ≥ 0.6 | 0.75 | pass |

Both Stage 2 (DSR) and Stage 3 (MaxDD) fail ⇒ `passed: false`.

---

## Honest reading (one paragraph)

The Stage-1 gross conditional drift (t=2.51 on `equity_riskon`) **does not survive** the staged
gate. Two independent kills fire. **Stage 2:** the deflated Sharpe is **0.0** — the per-trade
Sharpe of the vol-normalized episode trades does not beat the expected max of 6 zero-skill
trials, so there is no deflated risk-adjusted edge once multiple-comparisons deflation
(n_trials=6) is applied. **Stage 3:** the walk-forward path's max drawdown is **-30.14R**, just
over the frozen -30.0R budget (a 0.14R breach). The headline metrics look strong in isolation
(expectancy +1.28R/trade, PF 2.10, MAR 3.34, robust 0.75) — but the lane is a path-gated
procedure, not an average-gated one, and the path's drawdown breaches the budget while the
deflated Sharpe says the apparent edge is selection noise. This is the same structural-drawdown
wall every prior lane hit: a gross drift that evaporates under deflation + path discipline.
Consistent with the pre-registration's NEGATIVE expectation — the survival at Stage 1 was a
gross, pre-cost, single-family artifact, exactly as the gate is designed to catch.

---

## Disposition

**CLOSED NEGATIVE** at Stage 2/3 (human-gated session, 2026-06-26). Per the pre-registered kill
rule: fail ANY stage ⇒ closed, no v2. Stage 4 (transfer) and Stage 5 (forward) are NOT run — the
lane is dead. `--transfer`/`--forward` would only execute on a survivor that cleared Stage 2+3,
which does not exist.

No promotion path was ever touched (paper-only lane). `promotion/`, `journal/signals.jsonl`,
`EXIT_REGISTRY` untouched throughout.
