# Engine v3 - Backtest Evaluation - Pre-Registration (FROZEN)

**Instrument:** `tools/v3_evaluate.py` / `src/moonface/signal/engine/v3/evaluate.py`  
Spec: `docs/research-log/specs/2026-07-06-v3-eval-instrument-design.md`  
**Pinned `engine_hash_v3(EngineConfigV3())`:** `dccc879a51939ea02394f26ef944276b642089a88cbbab0803a478ece4e02893`  
**Registered:** 2026-07-06. Read-only; never gates capital.

## Frozen Splits

- Train: 2020-01-01 -> 2024-01-01
- Validation: 2024-01-01 -> 2025-07-01
- Sealed: 2025-07-01 -> 2026-07-01

## Fit

Isotonic per-mechanism q_floors + negative/underpowered cell pruning only.
Trigger params and the v2.2 ATR bracket (2.0/3.0/96/14) stay frozen.
Effective trials T = 12.

## Gates

1. Validation: net-R > 0 @ 3x cost; family-corrected block-CI lower bound > 0;
   max-drawdown-R <= v2.2; n >= 200.
2. Sealed BTC: net-R sign > 0 @ 3x cost; max-drawdown-R <= v2.2 sealed.
3. Transfer: net-R sign > 0 @ 3x cost on BOTH ETH and SOL (>= 20 trades each),
   fitted-BTC constants applied unchanged.

Verdict: `CLOSED_NEGATIVE_VALIDATION`, `CLOSED_NEGATIVE_SEALED_BTC`,
`CLOSED_NEGATIVE_TRANSFER`, or
`ALL_GATES_PASSED_HUMAN_DECISION_PENDING`.

## Discipline

One registered run; re-runs only for demonstrated mechanical failure. Sealed
touched only inside the gate flow, only if Gate 1 passes. A passing verdict
authorizes a human to re-freeze the fitted constants as a live candidate and
start a small paper allocation. It is not itself a deployment.
