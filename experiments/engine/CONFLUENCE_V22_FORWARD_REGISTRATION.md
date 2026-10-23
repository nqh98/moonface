# Confluence Engine v2.2 — Forward-Paper Pre-Registration

**STATUS: FROZEN (2026-07-05, human-approved v2.2 mandate).**
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration (v2.3).

Spec: `docs/research-log/specs/2026-07-05-v22-module-prune-design.md`.
Predecessor: `CONFLUENCE_V21_FORWARD_REGISTRATION.md` (SUPERSEDED addendum,
zero completed setups). Design evidence:
`experiments/engine/SCORING_AUDIT_2026-07.md` (Stage-1 trend
CURRENT_WEIGHTS_ADEQUATE / revert NO_SIGNAL; Stage-2 BOTH books NO_SIGNAL;
m4_pullback LOO-HARMFUL in both stages — the sole audit-licensed removal).

## Posture (binding)

Paper only. Disciplined heuristic, **no validated-edge claim** — the
NO_CLAIM banner rides on every emitted signal. v2.2 is a DEFENSIBILITY
improvement over v2.1, not a validated edge: Stage-2 of the scoring audit
showed even the trend book at NO_SIGNAL_IN_ANY_WEIGHTING on the
deriv-inclusive panel, and the audit measured m4-removal ordering only on
direction-stable bars. Single change vs v2.1: m4_pullback is excluded from
the trend book's score, breadth, and max_attainable (still scored and
journaled; with-m4 counterfactuals journal as `v2.2 m4_pullback excluded`
shadows). Threshold 60 / Tier-A 75 stay ABSOLUTE over the reduced max (85
with funding data, 70 without) — knowingly stricter, no new constants.
The mean_revert book remains shadow-only (v2.1 `VETO_NO_CT` mechanism,
unchanged); the audit's NO_SIGNAL verdict on that book is its standing
rationale. NOT tuned against history beyond this one registered removal.

## Frozen identity

- `ENGINE_VERSION = "2.2"`, `EXCLUDED_MODULES = ("m4_pullback",)` and
  `VETO_M4_EXCLUDED` folded into `engine_hash` with the other frozen
  module constants.
- `engine_hash = b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5`
- `enable_date_utc = 2026-07-05`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`, `lookback_bars = 6000`.
- Full test suite at freeze: 1862 passed, 3 skipped.

## Horizon (pre-committed)

Evaluate at the LATER of **6 months** from enable_date_utc OR **≥ 30
completed setups** (EXIT rows at the frozen hash). No interim
peeking-to-decide; one verdict, written once.

## Success bar (all must hold)

1. **Net R > 0** over all completed setups at the frozen hash.
2. **Drawdown within the layered budgets** — trailing 15R/90d window never
   beyond routine pause; the 30R hard latch never tripped.
3. **Mandatory ablation report** (part of the verdict, from the journal via
   `tools/engine_ablation.py`): per-family — `macro`, `no_ct`, `long_only`,
   `m4_pullback` — shadow-score distributions and counterfactual R.
   REPORTED, none gating. The `m4_pullback` family is the forward test of
   this registration's one change.

## Kill rule (binding)

One cycle. DOWNGRADE → `enabled=false`, no re-tune on this hash; any
constant change is v2.3 → new hash → new registration → fresh clock.

## Sanity replay (non-gating, house convention)

`tools/engine_honest_report.py` over 2020-01→2026-06 (deriv=None,
price-structure core), filled 2026-07-05 from
`experiments/engine/v22_sanity_honest_report.json` at the frozen hash:
130 closed trades (~20.0/yr), net +40.14R, PF 1.31, expectancy +0.31R,
win 38.5%; max realized DD −21.71R — state ACTIVE, neither the 30R hard
latch nor the trailing-window pause tripped over the full 6.5y. Recency:
first half +19.25R / second half +20.88R / last 365d +8.51R (PF 1.95,
11 trades) — the whole sample is observed, no frozen-window artifact.
Outliers: net +6.05R ex-best-3, −9.98R ex-best-5. Cost: survives 3×
(+8.51R), dies at 5×. Versus the v2.1 replay (167 trades, +41.16R, max DD
−27.94R): the stricter absolute threshold trades LESS (130 vs 167) as
predicted, gives up ~1R of net, and widens the DD headroom against the
30R latch (−21.71R vs −27.94R) while tripling 3×-cost survival
(+8.51R vs +3.07R). Recorded for audit only — NOT an edge claim, NOT a
gate.

## Enable runbook (human ops)

1. This file FROZEN + committed.
2. `promotion/engine.json` needs no change (config identical; only code
   constants moved).
3. Restart the watch daemon; the first journal row at the v2.2 hash starts
   the record. v2.1 rows remain in the journal under the retired hash
   (isolated by the version filter).
4. Do not touch frozen constants until the horizon.
