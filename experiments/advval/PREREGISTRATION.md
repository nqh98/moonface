# advval - adversarial-validation instrument (H3) - PRE-REGISTRATION

Frozen 2026-07-06T03:16:14.019000+00:00 BEFORE any data read. Spec:
`docs/research-log/specs/2026-07-06-freedata-addendum-design.md` (H3).

**Not an edge study.** Claim under test: the recurring IS->OOS sign-flip
failure signature across closed families reflects measurable distribution
shift. Instrument: per-cell adversarial AUC (era A = before 2024-01-10 UTC,
era B = after; spot-ETF approval). Retrodiction: per-study Spearman between
the study's cell AUC and its FLIP/NO_SIGNAL outcome.

## Frozen design

```json
{
  "symbol": "BTCUSDT",
  "funding_symbol": "BTC/USDT:USDT",
  "exchange": "binanceusdm",
  "metrics_field": "sum_open_interest",
  "window_start_ms": 1640995200000,
  "era_split_ms": 1704844800000,
  "cells": [
    "price_4h",
    "price_1d",
    "funding_8h",
    "oi_4h"
  ],
  "price_features": [
    "abs_ret_z",
    "close_loc",
    "log_ret",
    "range_frac",
    "up_frac_30",
    "vol_z"
  ],
  "funding_features": [
    "abs_rate_z",
    "pos_frac_30",
    "rate",
    "rate_chg",
    "rate_z"
  ],
  "oi_features": [
    "abs_chg_z",
    "oi_chg",
    "oi_chg30",
    "oi_chg_z"
  ],
  "z_window": 90,
  "gbt": {
    "rounds": 200,
    "lr": 0.1,
    "min_leaf": 20
  },
  "cv": {
    "n_folds": 5,
    "embargo": 90
  },
  "bootstrap": {
    "n_boot": 2000,
    "seed": 20260706
  },
  "kill_rule": "kill unless rho > 0 AND ci_low > 0 (90% percentile CI)",
  "window_end_ms": 1783307774019,
  "n_studies": 18,
  "registered_utc": "2026-07-06T03:16:14.019000+00:00"
}
```

## Frozen coding table (18 studies; FLIP=IS strength that reversed/decayed OOS, NO_SIGNAL=never strong)

| study | cell | outcome | basis |
|---|---|---|---|
| `xsection_mom_30` | price_1d | FLIP | passed screen+holdout (MAR 3.19); sealed tail −91.6% DD |
| `xsection_mom_7` | price_1d | FLIP | screen-positive; died in OOS holdout (−51% DD) |
| `xsection_carry_7` | funding_8h | FLIP | screen-positive; died in OOS holdout (−35% DD) |
| `bab_60` | price_1d | FLIP | IS anomaly (research MAR 1.93); holdout reverses (MAR −0.48) |
| `liqrev` | oi_4h | FLIP | first half +0.42%/event; second half ≈0 (time decay) |
| `practical_full_reeval` | price_4h | FLIP | 3/132 passed battery; ALL reversed in recent sealed window |
| `ls_tournament` | price_4h | FLIP | sole explore survivor reversed in sealed holdout |
| `bb_breakout_harvest` | price_4h | FLIP | alive in-sample lead failed gross Z floor once OOS-aware |
| `resrev_1` | price_1d | NO_SIGNAL | gross pre-screen coin flip (Z −0.18); never IS-strong |
| `oibuild_study` | oi_4h | NO_SIGNAL | pooled −0.64%/event; sign test 8/16 |
| `calseason` | price_4h | NO_SIGNAL | max |Z| 1.54 vs gate 3; never near gate |
| `system_search` | price_4h | NO_SIGNAL | 0/72 pass stage 1; top DSR 0.401 |
| `practical_discovery` | price_4h | NO_SIGNAL | 0/72 survivors |
| `drift_basket` | price_1d | NO_SIGNAL | research net −0.64; stages 1–3 fail |
| `pathsig_rung0` | price_4h | NO_SIGNAL | DSR 0 on all 30 rows |
| `dual_timeframe` | price_4h | NO_SIGNAL | all 9 cells die at gross-drift stage 1 |
| `multifamily_funding` | funding_8h | NO_SIGNAL | funding families mechanism_does_not_exist |
| `multifamily_oi` | oi_4h | NO_SIGNAL | OI families mechanism_does_not_exist |

## EXCLUDED studies (coding-scope record)

- `positioning_transfer` - asset-transfer failure, not time-OOS
- `funding_fade_transfer` - asset-transfer failure, not time-OOS
- `program_cycles_1_11` - drawdown-wall failure mode, predates the ladder
- `breadth*` - cross-asset features unmeasured; confound closure
- `macro_event` - exogenous data family unmeasured
- `exogenous` - exogenous data family unmeasured
- `bookdepth` - microstructure features unmeasured
- `aggtrades` - microstructure features unmeasured
- `taker_flow` - microstructure features unmeasured
- `donchian_4h_paper` - withdrawn, not closed negative
- `mtf_confluence` - still-open forward thread
- `btc_specialized` - composite engines, no single feature family
- `playbook` - composite engines, no single feature family
- `confluence engine` - composite engines, no single feature family

## Verdict rule (frozen)

**kill unless rho > 0 AND ci_low > 0 (90% percentile CI)** - a kill means adversarial validation is dead as an
instrument here: the harness keeps its existing gates and no pre-screen is
adopted. A pass adopts the AUC pre-screen for future pre-registrations only;
it rescues nothing and gates no live decision.

## Power note (honest)

Only 4 distinct AUC values map onto 18 studies, so rho is coarse by design;
the bootstrap CI over studies carries that granularity. This is the
pre-committed design; there is no post-hoc refinement path.
