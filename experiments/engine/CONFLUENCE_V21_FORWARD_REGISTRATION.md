# Confluence Engine v2.1 — Forward-Paper Pre-Registration

> **SUPERSEDED 2026-07-05 by v2.2** (audit-driven m4_pullback exclusion;
> see `CONFLUENCE_V22_FORWARD_REGISTRATION.md` and
> `SCORING_AUDIT_2026-07.md`). Withdrawn with ZERO completed setups at the
> v2.1 hash — the one-day record is uncontaminated; no verdict is claimed.

**STATUS: FROZEN (2026-07-04, human-approved v2.1 mandate).**
No frozen value below may change until the horizon; any change is a new
ENGINE_VERSION → new hash → new registration (v2.2).

Spec: `docs/research-log/specs/2026-07-04-confluence-engine-v21-design.md`.
Predecessor: `CONFLUENCE_V2_FORWARD_REGISTRATION.md` (SUPERSEDED addendum,
zero-trade record). Design evidence: `CALIBRATION_DIAGNOSTIC_2026-07.md`
(UNCALIBRATED; one-run rule stands — v2.1 gets no new historical calibration).

## Posture (binding)

Paper only. Disciplined heuristic, **no validated-edge claim** — the NO_CLAIM
banner rides on every emitted signal. v2.1 is an evidence-guided
SIMPLIFICATION of v2: no counter-trend entries, one tier (threshold 60,
fraction 0.005, high-vol halved), long-only. All three removals journal as
shadows so this registration's ablation can test them on forward data.
NOT tuned against history beyond the three registered removals.

## Frozen identity

- `ENGINE_VERSION = "2.1"`, folded into `engine_hash` with the frozen module
  constants (incl. `VETO_NO_CT`, `VETO_LONG_ONLY`, the flattened
  `_TIER_PROFILE_FRACTION`).
- `engine_hash = 4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a`
- `enable_date_utc = 2026-07-04`, `journal_path = journal/signals.jsonl`,
  `symbol/timeframe = BTC/USDT:USDT 1h`, `lookback_bars = 6000`.

## Horizon (pre-committed)

Evaluate at the LATER of **6 months** from enable_date_utc OR **≥ 30
completed setups** (EXIT rows at the frozen hash). No interim
peeking-to-decide; one verdict, written once.

## Success bar (all must hold)

1. **Net R > 0** over all completed setups at the frozen hash.
2. **Drawdown within the layered budgets** — trailing 15R/90d window never
   beyond routine pause; the 30R hard latch never tripped.
3. **Mandatory ablation report** (part of the verdict, from the journal via
   `tools/engine_ablation.py`): per-family — `macro`, `no_ct`, `long_only` —
   shadow-score distributions and counterfactual R. REPORTED, none gating.

## Kill rule (binding)

One cycle. DOWNGRADE → `enabled=false`, no re-tune on this hash; any constant
change is v2.2 → new hash → new registration → fresh clock.

## Sanity replay (non-gating, house convention)

`tools/engine_honest_report.py` over 2020-01→2026-06 (deriv=None,
price-structure core), filled 2026-07-04 from
`experiments/engine/v21_sanity_honest_report.json` at the frozen hash:
167 closed trades (~25.8/yr), net +41.16R, PF 1.25, expectancy +0.25R,
win 38.9%; max realized DD −27.94R — state ACTIVE, neither the 30R hard
latch nor the trailing-window pause tripped over the full 6.5y (v1/v2
latched in their first year). Recency: first half +9.99R / second half
+31.17R / last 365d +5.11R (PF 1.41) — the whole sample is observed, no
frozen-window artifact. Outliers: net +6.56R ex-best-3, −10.40R ex-best-5.
Cost: survives 3× (+3.07R), dies at 5×. Recorded for audit only — NOT an
edge claim, NOT a gate; the DD headroom (−27.94R vs the 30R latch) is thin.

## Enable runbook (human ops)

1. This file FROZEN + committed.
2. `promotion/engine.json` already carries `enabled: true` /
   `lookback_bars: 6000`; it needs no change (config identical, only code
   constants moved).
3. Restart the watch daemon; the first journal row at the v2.1 hash starts
   the record. The 5+ v2 WAIT rows remain in the journal under the retired
   hash (isolated by the version filter).
4. Do not touch frozen constants until the horizon.
