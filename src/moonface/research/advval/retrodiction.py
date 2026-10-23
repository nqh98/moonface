"""Frozen closed-study coding table and the retrodiction verdict.

Coding rule (frozen): FLIP (1) = the study's pre-registered research/IS phase
showed strength that reversed or decayed in its OOS/sealed/second-half
evaluation. NO_SIGNAL (0) = never showed strength at any stage. Studies whose
closure was a different failure mode are EXCLUDED and recorded below.

The falsifiable claim: cells with higher adversarial AUC should carry more
FLIP outcomes. Kill rule (frozen): kill unless rho > 0 AND ci_low > 0
(90% two-sided percentile bootstrap over studies, n_boot=2000, seed=20260706).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from moonface.core.stats import spearman
from moonface.kernel.bootstrap import iid_resample_randrange

CELLS = ("price_4h", "price_1d", "funding_8h", "oi_4h")
N_BOOT = 2000
SEED = 20260706
CI_LO_PCT = 5.0
CI_HI_PCT = 95.0


@dataclass(frozen=True)
class Study:
    name: str
    cell: str
    outcome: int
    basis: str


STUDIES: tuple[Study, ...] = (
    Study(
        "xsection_mom_30",
        "price_1d",
        1,
        "passed screen+holdout (MAR 3.19); sealed tail −91.6% DD",
    ),
    Study(
        "xsection_mom_7",
        "price_1d",
        1,
        "screen-positive; died in OOS holdout (−51% DD)",
    ),
    Study(
        "xsection_carry_7",
        "funding_8h",
        1,
        "screen-positive; died in OOS holdout (−35% DD)",
    ),
    Study(
        "bab_60",
        "price_1d",
        1,
        "IS anomaly (research MAR 1.93); holdout reverses (MAR −0.48)",
    ),
    Study(
        "liqrev",
        "oi_4h",
        1,
        "first half +0.42%/event; second half ≈0 (time decay)",
    ),
    Study(
        "practical_full_reeval",
        "price_4h",
        1,
        "3/132 passed battery; ALL reversed in recent sealed window",
    ),
    Study(
        "ls_tournament",
        "price_4h",
        1,
        "sole explore survivor reversed in sealed holdout",
    ),
    Study(
        "bb_breakout_harvest",
        "price_4h",
        1,
        "alive in-sample lead failed gross Z floor once OOS-aware",
    ),
    Study(
        "resrev_1",
        "price_1d",
        0,
        "gross pre-screen coin flip (Z −0.18); never IS-strong",
    ),
    Study(
        "oibuild_study",
        "oi_4h",
        0,
        "pooled −0.64%/event; sign test 8/16",
    ),
    Study(
        "calseason",
        "price_4h",
        0,
        "max |Z| 1.54 vs gate 3; never near gate",
    ),
    Study(
        "system_search",
        "price_4h",
        0,
        "0/72 pass stage 1; top DSR 0.401",
    ),
    Study(
        "practical_discovery",
        "price_4h",
        0,
        "0/72 survivors",
    ),
    Study(
        "drift_basket",
        "price_1d",
        0,
        "research net −0.64; stages 1–3 fail",
    ),
    Study(
        "pathsig_rung0",
        "price_4h",
        0,
        "DSR 0 on all 30 rows",
    ),
    Study(
        "dual_timeframe",
        "price_4h",
        0,
        "all 9 cells die at gross-drift stage 1",
    ),
    Study(
        "multifamily_funding",
        "funding_8h",
        0,
        "funding families mechanism_does_not_exist",
    ),
    Study(
        "multifamily_oi",
        "oi_4h",
        0,
        "OI families mechanism_does_not_exist",
    ),
)

EXCLUDED: tuple[tuple[str, str], ...] = (
    ("positioning_transfer", "asset-transfer failure, not time-OOS"),
    ("funding_fade_transfer", "asset-transfer failure, not time-OOS"),
    ("program_cycles_1_11", "drawdown-wall failure mode, predates the ladder"),
    ("breadth*", "cross-asset features unmeasured; confound closure"),
    ("macro_event", "exogenous data family unmeasured"),
    ("exogenous", "exogenous data family unmeasured"),
    ("bookdepth", "microstructure features unmeasured"),
    ("aggtrades", "microstructure features unmeasured"),
    ("taker_flow", "microstructure features unmeasured"),
    ("donchian_4h_paper", "withdrawn, not closed negative"),
    ("mtf_confluence", "still-open forward thread"),
    ("btc_specialized", "composite engines, no single feature family"),
    ("playbook", "composite engines, no single feature family"),
    ("confluence engine", "composite engines, no single feature family"),
)


def retrodiction_verdict(
    cell_aucs: dict[str, float],
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> dict:
    xs = [cell_aucs[s.cell] for s in STUDIES]
    ys = [float(s.outcome) for s in STUDIES]
    rho = spearman(xs, ys)
    if rho is None:
        return {
            "rho": None,
            "ci_low": None,
            "ci_high": None,
            "n_studies": len(STUDIES),
            "verdict": "kill",
            "reason": "degenerate_spearman",
        }

    rng = random.Random(seed)
    n = len(STUDIES)
    draws: list[float] = []
    for _ in range(n_boot):
        idx = iid_resample_randrange(rng, list(range(n)))
        r = spearman([xs[i] for i in idx], [ys[i] for i in idx])
        if r is not None:
            draws.append(r)

    draws.sort()

    def pct(p: float) -> float:
        if not draws:
            return float("nan")
        pos = (len(draws) - 1) * p / 100.0
        lo = int(pos)
        hi = min(lo + 1, len(draws) - 1)
        return draws[lo] + (draws[hi] - draws[lo]) * (pos - lo)

    ci_low = pct(CI_LO_PCT)
    ci_high = pct(CI_HI_PCT)
    ok = rho > 0.0 and ci_low > 0.0
    return {
        "rho": rho,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n_studies": len(STUDIES),
        "verdict": "pass" if ok else "kill",
        "reason": "" if ok else "rho_or_ci_not_positive",
    }
