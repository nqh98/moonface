# forced_flow — STATUS (2026-07-13)

## Measurable today

Nothing gate-able. Funding/OI caches are healthy (funding 2020-01→2026-06; 5-min OI
2020-09→2026-07) but **Axis F is VOID** (≥50% overlap with microscope / SSE Track L /
regime_moe nulls — see `docs/research-log/concepts/gravitational_universe_model_ANALYSIS.md` §1). The fieldmap
architecture exists on paper only; no code is built until an axis has data.

The one available empirical read is the **COIN-M BTCUSD_PERP pilot** on the frozen keyless
archive (2023-06-25 → 2024-10-14): registration drafted, not approved, nothing run.

## Blocked until when

| Axis | Blocker | Unblocks |
|---|---|---|
| Axis L, USDⓈ-M BTCUSDT | forward accrual only (no keyless history exists anywhere) — collector restarted 2026-07-13 with reconnect + flock-watchdog fixes (commit 1ccae38); verify accrual in `experiments/newdata/liquidations/manifest.json`, never assume it is running | readiness gate ≥180 d / ≥200 clusters / coverage ≥0.90 → **~2027-01-09** |
| Dealer gamma | Deribit chain accrual (collector live since 2026-07-03) | **~2027-01** |
| Axis F | permanently void (overlap clause) | — |

## Single next decision point

**Human sign-off on `experiments/forced_flow/PILOT_COINM_REGISTRATION.md` (D3 gate).**
Until then: no pilot code, no downloads, no runs. If declined, the lane simply waits for the
~2027-01-09 readiness gate. Verdicts, when they come, are written once and are terminal.
