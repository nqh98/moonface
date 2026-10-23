# euphoria_fade v1 — RESULTS (2026-07-11)

Registration: PREREGISTRATION.md (frozen 2026-07-10, commit 1f94d1b).
Run: seed 1, cache/matrix, 2020-01-01 → 2026-07-01, offline, bookdepth skipped.

**VERDICT: CLOSED_NEGATIVE** — well-powered clean fail. p=1 is negative
already in-sample (n=658, exp −0.0195) and worse OOS (n=408, exp −0.1078).
p=2 clears the IS screen (n=344, exp +0.0515) but reverses OOS (n=219, exp
−0.0973) and — decisively — is *worse than its own control* (−0.0973 vs
−0.0633): removing the crowding gate loses less, so "euphoria" subtracts
information from plain "hot uptrend". DSRs 0.001 / 0.217 vs the 0.95 gate.
Null calibration is healthy: 0/200 draws pass the gate in both cells, so the
FAIL is not a tautology — the gate genuinely discriminates and the real
signal genuinely isn't there. **Lockbox sealed/UNSPENT** (208 + 114 treatment
trades never examined). Directional read: going long into the euphoria cell
lost (the microscope texture) *and* shorting it loses too — the cell is
high-churn noise, not an exhaustion edge.

| cell | n_IS | exp_IS | n_OOS | exp_OOS | exp_ctrl_OOS | DSR | null pass-rate | s1 | s2 | s3 | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p=1 | 658 | -0.0195 | 408 | -0.1078 | -0.0898 | 0.001 | 0.000 | FAIL | FAIL | FAIL | FAIL |
| p=2 | 344 | +0.0515 | 219 | -0.0973 | -0.0633 | 0.217 | 0.000 | PASS | FAIL | FAIL | FAIL |

Per the registration: the euphoria/crowding-fade family is terminal — no v2,
no threshold tuning, no direction flip, no long-veto rescue, no fishing in
the other 13 buckets. The microscope texture is recorded as noise, closing
the loop `experiments/microscope/FINDINGS.md` left open.
