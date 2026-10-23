# euphoria_fade v1 — run report (stages 1-4; lockbox SEALED)

Registered: PREREGISTRATION.md (frozen 2026-07-10). Best possible
outcome is FORWARD PAPER registration (contamination cap).

Verdict: **CLOSED_NEGATIVE**

| cell | n_IS | exp_IS | n_OOS | exp_OOS | exp_ctrl_OOS | DSR | null pass-rate | s1 | s2 | s3 | s4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p=1 | 658 | -0.0195 | 408 | -0.1078 | -0.0898 | 0.001 | 0.000 | FAIL | FAIL | FAIL | FAIL |
| p=2 | 344 | +0.0515 | 219 | -0.0973 | -0.0633 | 0.217 | 0.000 | PASS | FAIL | FAIL | FAIL |

Lockbox is one-touch: `lockbox` subcommand, only when a cell
passes stages 1-4. Kill rule on any failure: family terminal.
