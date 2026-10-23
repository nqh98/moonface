# v3 Backtest Evaluation Instrument — Design

**Status:** design approved, spec under review
**Date:** 2026-07-06
**Engine under test:** v3 regime-mechanism engine
(`docs/research-log/specs/2026-07-06-regime-mechanism-engine-v3-design.md`,
plumbing-validated via `tools/v3_replay.py`).

## 1. Goal

Produce a **verdict on v3 in days, not months**, without the winner's-curse
trap. A pre-registered, read-only instrument that: fits a *minimal* set of v3
constants on a train window, selects/kills on a validation window, and confirms
**once** on a sealed latest-year window plus an ETH/SOL transfer test — all
judged apples-to-apples against the frozen v2.2 incumbent.

It **never gates capital and never edits the engine.** It emits a fitted-v3
candidate + a verdict. Promotion (re-freezing the fitted constants as a live
v3.1) is a separate human decision, and only reachable if every gate passes.

### Non-goals

- Not a replacement for the frozen forward-paper registration; a passing
  verdict means "small-size paper/live candidate," **not** "proven edge."
- No fitting beyond the Minimal scope in §4. No per-asset re-fitting.
- No edits to `config_v3.py`, `decide.py`, or any committed v3 engine file; the
  engine is consumed as-is.

## 2. Instrument shape & module layout

New files only:

```
src/moonface/signal/engine/v3/evaluate.py   fit -> gate flow -> verdict (analysis)
tools/v3_evaluate.py                         thin CLI: load bundles, write report JSON
experiments/engine/ENGINE_V3_EVAL_2026-07.md FROZEN pre-registration
```

Modeled on `repair.py`: pure analysis functions, a single
`build_eval_report(...)` orchestrator, JSON-serializable output, sealed segment
touched **only** inside the gate flow.

## 3. Frozen splits, assets, and baseline

All boundaries are frozen constants in `evaluate.py`, tested verbatim.

- **Data span:** `1577836800000` (2020-01-01) → `1782316800000` (2026-07-01),
  BTC/USDT:USDT 1h.
- **Train:** exit `< 1704067200000` (2024-01-01). Fit only.
- **Validation:** entry `≥ train_end + purge`, exit `< 1751328000000`
  (2025-07-01). Select/kill.
- **Sealed:** entry `≥ 1751328000000 + purge`, → span end. One look.
- **Purge:** `168 * 3_600_000` (== `repair.PURGE_MS`) between segments.
- **Cross-asset sealed:** ETH/USDT:USDT and SOL/USDT:USDT, same sealed window.
- **Baseline:** frozen v2.2 (hash `b4924f8e…`) over the identical windows,
  net-R and max-drawdown-R, via the existing v2.2 trade path.

**Sealed protection:** the sealed segment (and ETH/SOL) is evaluated only if the
candidate survives Gate 1; a validation death never spends the sealed bullet.

## 4. Fit — Minimal scope (deterministic, low-df)

Two fitted things only; all trigger params and the exit bracket stay frozen.

### 4.1 Trade construction (shared by fit and gates)

`decide_v3` is stateless, so trades come from a **one-position-at-a-time**
sequential simulator:

- Walk bars on a bounded trailing window (as in `replay.py`). When **flat** and
  `decide_v3` returns `ENTER`, open a trade; **skip every signal while a
  position is open.**
- **Exit = frozen v2.2 ATR bracket, reused verbatim:** `k_stop=2.0`,
  `k_trail=3.0`, `max_bars=96`, `atr_period=14` (frozen constants in
  `evaluate.py`; not fitted). Both v3 and the v2.2 baseline exit identically, so
  the comparison isolates *entry selection*.
- Each trade records `entry/exit index+ts, direction, mechanism, quality,
  risk_fraction, net_r, bars_held, exit_reason`. `net_r` is realized R;
  `risk_fraction` (the size-only score) weights the trade's contribution to
  portfolio metrics.

### 4.2 q_floor per mechanism (isotonic; `repair.py` C3 pattern)

For each mechanism, take its TRAIN trades as `(quality, net_r)`; PAVA-fit `E[R]`
monotone in quality; set `q_floor` = the lowest quality where fitted
`E[R] ≥ 0`. No grid search — the curve determines the floor. A mechanism with
fewer than `MIN_MECH_TRADES = 30` train trades keeps its default floor.

### 4.3 Cell pruning

For each of the 9 active matrix cells, compute TRAIN net-R of that cell's
trades. If the sign is `≤ 0`, or the cell has fewer than
`MIN_CELL_TRADES = 30` trades, prune it to `None` (stand flat). The result is a
fitted matrix (a copy; the frozen `REGIME_MECHANISM` is untouched).

### 4.4 Fitted candidate & effective trial count

The fit yields `fitted_cfg` (3 q_floors) + `fitted_matrix` (≤ 9 live cells).
**Effective trial count** `T = N_MECHANISMS (3) + N_ACTIVE_CELLS (9) = 12` —
countable, no hand-waving — used to deflate the DSR in Gate 1.

**No-lookahead:** every fitter consumes TRAIN trades only (exit before
`train_end`); asserted by a spy test on the fitter inputs (`repair.py` pattern).

## 5. Gate — pre-registered, all-required

### Gate 1 — Validation (BTC)

1. Net-R **> 0 after 3× cost stress** (`honesty.cost_stress`).
2. **Deflated DSR:** block-bootstrap per-trade R with a *quantile-parameterized*
   CI (the `repair.block_ci_q` pattern, 168h blocks — `audit.block_ci` is
   fixed-95% and cannot express the family correction); family-correct by
   `T = 12` via `CI_LO_Q = 0.05 / T / 2`; the lower CI must be **> 0**.
3. Max-drawdown-R **no worse than v2.2** on the identical validation window.
4. Requires `≥ PANEL_FLOOR` validation trades (else fail).

### Gate 2 — Sealed BTC (opened once)

Net-R sign **positive after 3× cost** AND max-drawdown-R **≤ v2.2 sealed
baseline**. Sign + drawdown only — one year is too thin for a DSR claim.

### Gate 3 — Cross-asset transfer (ETH & SOL, same sealed year)

The fitted-BTC constants, applied **unchanged**, must produce **sign-positive
net-R after cost on both ETH and SOL.** No per-asset re-fitting. A below-floor
sample (`< MIN_TRANSFER_TRADES = 20` on an asset) **fails** the gate — thin data
cannot confirm.

### Verdict routing

| Outcome | Verdict |
|---|---|
| Fails Gate 1 | `CLOSED_NEGATIVE_VALIDATION` |
| Passes 1, fails sealed BTC | `CLOSED_NEGATIVE_SEALED_BTC` |
| Passes 1–2, fails ETH/SOL | `CLOSED_NEGATIVE_TRANSFER` |
| All pass | `ALL_GATES_PASSED_HUMAN_DECISION_PENDING` |

Only the last is a green light, and it means a **small-size candidate**, not a
proven edge.

## 6. Report

`build_eval_report(...)` returns a JSON-serializable dict: `engine_hash_v3`,
`label`, `data` (candles/fingerprint/span per asset), `frozen_constants`
(splits, purge, exit bracket, floors, `T`, CI quantiles), `segments` (counts +
dropped), `fitted` (q_floors + pruned matrix + trial count), `baseline_v22`
(validation + sealed net-R/maxDD), `gate1`, `gate2`, `gate3`, and `verdict`.
Downstream `gate2`/`gate3` are `null` when a prior gate closes the verdict.

## 7. Testing strategy

Hermetic, stdlib + pytest, synthetic candles (extend `tests/helpers_v3.py`):

- **Splits:** boundary/purge/drop cases (a trade spanning a boundary is
  dropped), frozen-constant assertions.
- **Trade sim:** one-position-at-a-time (no overlap), long and short brackets,
  stop/trail/target/max_bars exits produce correct `exit_reason` and `net_r`.
- **Fit:** q_floor rises to exclude a quality band with negative train E[R];
  underpowered mechanism keeps default; a negative-sign cell is pruned, a
  positive one kept; `T` computed correctly.
- **No-lookahead:** spy asserts every fitter input trade exits before
  `train_end`.
- **Gates:** synthetic panels that pass/fail each gate independently;
  deflated-CI is wider than the 95% CI; below-floor samples fail; sealed/ETH/SOL
  not computed when Gate 1 closes.
- **Report:** verdict routing for all four outcomes; JSON round-trips; sealed
  protection holds.

## 8. Discipline

Pre-registration `ENGINE_V3_EVAL_2026-07.md` FROZEN (all §3–§5 constants + the
pinned `engine_hash_v3`) **before** the sealed year is touched. One registered
run; re-runs only for demonstrated mechanical failure. Fitting sees train only.
A passing verdict authorizes a **human** to re-freeze the fitted constants as a
live candidate and start a small paper allocation — it is not itself a
deployment.
