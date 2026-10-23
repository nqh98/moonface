# BTC Multi-Timeframe Trend Playbook — Signal Engine

## Verdict: NEGATIVE

- asof: 2026-06-22T08:45:18.316140+00:00
- data_sha: 1h=13ff327d94d966dd, 2h=8de450095ac5cf18, 4h=b3b004cb58258369
- gate: explore(reported DSR) -> conjunctive selection -> dual replication (validate AND sealed, same sign); DSR NOT gated

| config | val_pf | val_exp | seal_pf | seal_exp | verdict |
|---|---|---|---|---|---|


## Why the table is empty (selection-stage NEGATIVE)

0 of 12 configs cleared the conjunctive selection battery, so **nothing was
carried to the sealed OOS gate** — the two sealed segments were never opened
(tail integrity preserved). The verdict is decided at selection, not validation.

In-sample (60% segment, ~2020-01→2023) the two best configs showed apparent
drift but failed three robustness gates each:

| config | n_trades | exp_R | PF | DD_R | rejected by |
|---|---|---|---|---|---|
| slope20:don55:chandelier | 28 | +0.346 | 1.33 | -9.7 | trades<30, outlier-dependent, recent-20% exp -1.94R (n=3) |
| slope20:don55:donchian_trail | 28 | +0.272 | 1.22 | -10.0 | trades<30, outlier-dependent, recent-20% exp -2.01R (n=3) |

The remaining 10 configs (slope10 or don20 variants) had PF<1.15 / negative
expectancy outright. This is the program's recurring signature: thin,
outlier-driven, already-decaying in-sample drift — not a robust signal. Both
survivors passed the +5bps cost-stress (PF 1.24 / 1.14), so cost was **not** the
killer; sample size, outlier-dependence, and recent decay were.

## Honest caveat

A NEGATIVE is the expected, valid outcome. Any accepted candidate is a single-asset BTC PAPER ONLY signal — it does NOT authorize live capital or automatic execution, must get its own frozen paper-forward protocol, and never inherits the live/Donchian slot. The frozen 4h Donchian Slice-3 strategy is untouched by this lane.
