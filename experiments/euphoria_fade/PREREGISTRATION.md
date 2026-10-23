# euphoria_fade v1 — Pre-Registration

Frozen **before any out-of-sample evaluation** (2026-07-10). A changed design
requires a new experiment directory. Design spec:
`docs/research-log/specs/2026-07-10-euphoria-fade-design.md` (local).
Origin: the sole replicated microscope texture
(`experiments/microscope/FINDINGS.md`) — explicitly flagged within-null across
14 buckets, so the prior is LOW and this lane is built to fail cleanly.

## 1. Hypothesis
On the 16-asset + BTC 4h perp universe (`tools/microscope.py:UNIVERSE`), an
asset's transition into the `UP/HIGH/CROWDED_LONG` regime cell (microscope
`label_series`, frozen thresholds `TREND_THR=0.5 / VOL_THR=0.5 /
CROWD_THR=1.0`, crowding = mean of `funding_z`,`oi_chg_z`) marks locally
exhausted demand. Direction is pre-committed **SHORT**, filled at the open of
the bar after the transition completes. Exit
`fixed_bracket{k_stop:2.0, m_tp:1.0, atr_period:14}` (stop-first intra-bar
tie-break), fraction 0.01, cost frozen 0.0006 all-in round-trip. One trade
per symbol per label episode. No microscope threshold may be tuned.

## 2. Treatment vs control (the one variable)
Grid = 2 treatment cells: persistence `p ∈ {1,2}` consecutive in-cell bars
before entry. Control (per p) = identical everything with the crowding gate
removed (transition into `UP/HIGH/*`). Controls are reference baselines, not
trials. `n_trials = 2`.

## 3. Windows
IS screen 2020-01-01→2023-12-31; OOS holdout 2024-01-01→2025-06-30;
one-touch lockbox 2025-07-01→2026-06-30. Feature matrix built once over the
full window (causal, trailing z-windows); trades partitioned by entry-bar
timestamp. Data: existing `cache/matrix`, offline, bookdepth skipped.

## 4. Evaluation ladder
1. Screen (IS): ≥30 trades pooled across symbols, net expectancy_R > 0.
2. Holdout: net expectancy_R > 0, MAR > 0, MaxDD ≥ −0.30 (f=0.01 curve),
   strict dominance over the same-p control on net expectancy_R.
3. DSR ≥ 0.95, n_trials = 2.
4. Null calibration (mandatory): ≥200 count-matched random-entry draws per
   symbol per window (uniform over non-UNLABELED bars), frozen pipeline;
   real IS+OOS pooled expectancy_R > null p95, AND the null must fail
   stages 1–2 at ~nominal rate — a gate the null passes voids the lane.
5. Lockbox (one-touch, opened only if 1–4 all pass): ≥20 trades, net
   expectancy_R > 0, MaxDD ≥ −0.30, dominance over control.

## 5. Contamination cap
The texture was discovered on data through 2026-06; the entire backtest,
lockbox included, overlaps discovery (partial independence only: discovery
statistic was unconditional long forward-R of Donchian events, not a
standalone short with brackets and costs). Frozen consequence: the best
possible outcome is **FORWARD PAPER registration** — live deployment can
never be justified from this lane's backtest.

## 6. Decision
→ FORWARD_PAPER_REGISTERED for any cell clearing all five stages: frozen
forward paper registration, no capital, review at ≥30 forward setups or 6
months.
→ CLOSED NEGATIVE otherwise. Kill rule: the euphoria/crowding-fade family is
terminal — no v2, no threshold tuning, no direction flip, no long-veto
rescue, no grid expansion, no fishing in the other 13 regime buckets. The
microscope texture is then recorded as noise.
