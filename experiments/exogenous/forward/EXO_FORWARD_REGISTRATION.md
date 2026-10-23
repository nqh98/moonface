# Exogenous-Conditioned BTC State Model -- Forward Registration

**Status:** TEMPLATE (no survivor exists at preregistration time)

This document binds the Stage-5 forward paper watch once a candidate survives
Stages 0-4. All values below are PLACEHOLDERS to be filled only when a
survivor exists and reaches Stage 5.

---

## Binding

This forward registration is frozen at the moment `t0_ms` is set. No
retroactive changes to the forward rule, window, or thresholds are permitted.

---

## Frozen Forward Rule

From `src/moonface/research/exogenous/forward.py`:

| Constant | Value |
|----------|-------|
| `FORWARD_MIN_TRADES` | `20` |
| `FORWARD_MIN_WEEKS` | `12.0` |
| `MAX_DD_BUDGET` | `0.30` |

### Outcomes

| Outcome | Condition |
|---------|-----------|
| `REAFFIRM` | net_r > 0 AND closed_trades >= 20 AND elapsed_weeks >= 12.0 AND drawdown >= -0.30 |
| `DOWNGRADE_DD` | drawdown < -0.30 (first-priority failure) |
| `DOWNGRADE_HORIZON` | min trade/week counts met but gate not passed (drawdown ok, net_r <= 0) |
| `INCONCLUSIVE` | insufficient trades (< 20) or elapsed time (< 12 weeks) |

---

## Placeholders (fill when survivor exists)

- **Surviving state:** (none)
- **t0_ms:** (set when forward watch begins)
- **now_ms:** (set at evaluation time, typically `end_ms` or current timestamp)
- **State parameters:** (copy from frozen_candidates.json)

---

## Evaluation

Run via: `tools/exogenous_btc.py --forward`

The forward report is computed by `forward_report(trades, t0_ms, now_ms)` and
emits the `outcome` field per the table above. The outcome is final once
`FORWARD_MIN_WEEKS` and `FORWARD_MIN_TRADES` are both satisfied.
