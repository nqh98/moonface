"""Economic bar: deploy/pass verdict from walk-forward test windows.

Replaces the academic DSR>0.95 gate. Drawdown tolerance is a user-set parameter
(not a fixed -15R cap): at risk_fraction f=0.01, 1R <-> 1% of capital, so a 30%
max-drawdown tolerance == 30R. MAR is R-based and f-independent.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.metrics import Summary


@dataclass(frozen=True)
class EconBar:
    profit_factor: float
    expectancy_r: float
    mar_floor: float
    max_dd_r: float        # at f=0.01, equals the % drawdown tolerance
    robust_frac: float


ECON_BAR = EconBar(profit_factor=1.2, expectancy_r=0.05, mar_floor=0.5,
                   max_dd_r=30.0, robust_frac=0.6)


@dataclass(frozen=True)
class EconVerdict:
    passed: bool
    reasons: list[str]
    metrics: dict


def _mar(s: Summary) -> float:
    if s.max_drawdown_r == 0:
        return 0.0
    return abs(s.total_r) / abs(s.max_drawdown_r)


def _window_robust(s: Summary) -> bool:
    return s.profit_factor > 1.0 and s.expectancy_r > 0.0


def evaluate_econ(test_summaries: list[Summary], aggregated: Summary,
                  bar: EconBar = ECON_BAR) -> EconVerdict:
    reasons: list[str] = []
    metrics = {
        "expectancy_r": aggregated.expectancy_r,
        "profit_factor": aggregated.profit_factor,
        "mar": round(_mar(aggregated), 4),
        "max_dd_r": aggregated.max_drawdown_r,
        "robust_frac": 0.0,
    }
    if aggregated.expectancy_r < bar.expectancy_r:
        reasons.append(f"expectancy {aggregated.expectancy_r} < {bar.expectancy_r}")
    if aggregated.profit_factor < bar.profit_factor:
        reasons.append(f"profit factor {aggregated.profit_factor} < {bar.profit_factor}")
    if _mar(aggregated) < bar.mar_floor:
        reasons.append(f"MAR {_mar(aggregated)} < {bar.mar_floor}")
    if abs(aggregated.max_drawdown_r) > bar.max_dd_r:
        reasons.append(f"drawdown {aggregated.max_drawdown_r}R exceeds {bar.max_dd_r}R tol")
    if test_summaries:
        frac = sum(1 for s in test_summaries if _window_robust(s)) / len(test_summaries)
        metrics["robust_frac"] = round(frac, 4)
        if frac < bar.robust_frac:
            reasons.append(f"robust in {frac:.0%} of windows < {bar.robust_frac:.0%}")
    passed = not reasons
    if passed:
        reasons = ["all thresholds met"]
    return EconVerdict(passed=passed, reasons=reasons, metrics=metrics)
