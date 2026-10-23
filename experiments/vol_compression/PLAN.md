# Vol Compression → Expansion Baseline — Implementation Plan

> Implemented autonomously (user: "apply your recommend, do not ask again") in one pass, TDD.
> This records the task breakdown; the authoritative frozen spec is `DESIGN.md`.

**Goal:** Isolated numpy/pandas prototype that detects volatility squeezes on BTC 1h and scores a direction-agnostic straddle-proxy payoff (priced off the compressed vol), gated on a sealed-OOS block-bootstrap CI (`min_n=30 > block=20`).

**Tech Stack:** Python 3.12, numpy, pandas; own venv `experiments/vol_compression/.venv`; quarantined.

## Global Constraints

- numpy + pandas only; not in root `pyproject.toml`; own venv.
- Causal: `RV_N(t)` from returns ≤ t; compression threshold from window ending t−1 (`.shift(1)`); only the payoff `|move|` over t→t+H looks ahead.
- Frozen params: `rv_period=24`, `comp_window=30d`, `comp_pct=20`, `cooldown=24`, `H=24 (1d) gated / 48 (2d) secondary`, `premium=√(2/π)·RV·√H`, `cost=0.0006`.
- Frozen split: in-sample `2020-01-01→2024-06-30`; sealed OOS `2024-07-01→present`.
- Frozen gate: block-bootstrap (block 20, 10k, seed 0) 95% CI lower bound > 0 on OOS mean 1d net payoff; `min_n=30`.
- Commit messages: no AI-attribution trailers.

---

### Task 1 — Scaffold + loader + feature helpers
Files: `requirements.txt`, `README.md`, `.gitignore`, `vol_compression_backtest.py`, `tests/conftest.py`, `tests/test_vol_compression.py`.
Produces `load_data`, `log_returns`, `realized_vol`, `atr_pct`, `rolling_pct_threshold`.
Tests: `test_load_data_parses_utc`, `test_log_returns_and_realized_vol`.

### Task 2 — Compression trigger + cooldown
Produces `_apply_cooldown`, `VolCompressionStrategy.feature_vol`, `.compression_signals` (RV/ATR squeeze ≤ 20th-pct of trailing window, then 24-bar cooldown).
Tests: `test_compression_fires_calm_not_high_vol`, `test_apply_cooldown_logic`, `test_threshold_no_future_leak`.

### Task 3 — Straddle-proxy payoff (tautology guard)
Produces `straddle_payoffs` → per-signal `net_h = |ln(close[i+h]/close[i])| − √(2/π)·sigma[i]·√h − cost`.
Tests: `test_payoff_nets_to_minus_cost_at_fair_move` (under the null net == −cost), `test_payoff_positive_when_expansion_beats_premium`, `test_right_edge_dropped`.

### Task 4 — Bootstrap + stats + verdict
Produces `block_bootstrap_ci` (hardened, `min_n>block`), `compute_payoffs`, `slice_stats`, `verdict`, `format_tear_sheet`.
Tests: `test_block_bootstrap_ci_non_degenerate_when_n_gt_block`, `test_block_bootstrap_ci_empty_is_nan`, `test_verdict_branches`, `test_slice_stats_keys`.

### Task 5 — CLI
Produces `main` — full-series payoffs, split at `--oos-cutoff`, print both tear-sheets + verdict off OOS 1d CI. Flags per DESIGN §7.
Test: `test_main_runs_and_prints_verdict`.

### Task 6 — Registered run + RESULTS.md (opens the seal ONCE)
Run `--feature rv` (primary) and `--feature atr` (robustness); write `RESULTS.md` with both tear-sheets, verdict, CIs, robustness read, honest interpretation. Do not re-run altered params to change the verdict.

---
Status: Tasks 1–5 implemented, 13/13 tests green. Task 6 = the sealed run.
