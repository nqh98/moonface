"""Train selection and validate/sealed verdict for the breadth lane."""
from __future__ import annotations

from collections.abc import Callable

from moonface.core.metrics import COST_FRACTION, Summary, summarize_r
from moonface.research import system_battery as sb
from moonface.research.breadth.evaluate import evaluate_cell
from moonface.research.breadth.grid import BreadthCell
from moonface.research.breadth.signals import _ALWAYS
from moonface.kernel.econ import ECON_BAR, evaluate_econ
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR

DSR_THRESHOLD = 0.95
EXTRA_COST = 0.0005


def cost_stress(records: list[dict], extra_cost: float) -> dict:
    stressed = [
        r["net_r"] - extra_cost / r["atr_frac"] if r["atr_frac"] > 0 else r["net_r"]
        for r in records
    ]
    s = summarize_r(stressed)
    return {
        "expectancy_r": s.expectancy_r,
        "profit_factor": s.profit_factor,
        "passed": s.expectancy_r > 0 and s.profit_factor > 1.0,
    }


def cost_multiple(records: list[dict], mult: float) -> dict:
    return cost_stress(records, (mult - 1.0) * COST_FRACTION)


def practical_pass(metrics: dict) -> bool:
    return (
        metrics["profit_factor"] >= PF_FLOOR
        and metrics["expectancy_r"] > 0
        and abs(metrics["max_drawdown_r"]) <= MAX_DD_R
        and metrics["trade_count"] >= MIN_TRADES
    )


def _econ_summary(metrics: dict) -> Summary:
    return Summary(
        trade_count=metrics["trade_count"],
        win_rate=0.0,
        expectancy_r=metrics["expectancy_r"],
        profit_factor=metrics["profit_factor"],
        max_drawdown_r=metrics["max_drawdown_r"],
        total_r=metrics["total_r"],
    )


def select_survivors(
    daily,
    btc_train,
    cells: list[BreadthCell],
    explore_rows: list[dict],
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> list[BreadthCell]:
    dsr_by_key = {row["key"]: row.get("dsr", 0.0) for row in explore_rows}
    by_family: dict[str, list[BreadthCell]] = {}
    for cell in cells:
        by_family.setdefault(cell.family, []).append(cell)
    for family_cells in by_family.values():
        family_cells.sort(key=lambda c: c.axis)

    survivors: list[BreadthCell] = []
    for cell in cells:
        evaluated = evaluate_cell(daily, btc_train, cell, is_member)
        metrics = evaluated["metrics"]
        records = evaluated["records"]
        if not practical_pass(metrics):
            continue
        if not cost_stress(records, EXTRA_COST)["passed"]:
            continue
        if not cost_multiple(records, 2.0)["passed"]:
            continue
        if not cost_multiple(records, 3.0)["passed"]:
            continue
        if not sb.outlier_dependence_ok([r["net_r"] for r in records], 0.05)["passed"]:
            continue
        if dsr_by_key.get(cell.key, 0.0) < DSR_THRESHOLD:
            continue

        members = by_family[cell.family]
        idx = next(i for i, member in enumerate(members) if member.key == cell.key)
        island = any(
            0 <= j < len(members)
            and practical_pass(evaluate_cell(daily, btc_train, members[j], is_member)["metrics"])
            for j in (idx - 1, idx + 1)
        )
        if island:
            survivors.append(cell)
    return survivors


def validate_cell(
    daily,
    btc_val,
    btc_seal,
    cell: BreadthCell,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    validate = evaluate_cell(daily, btc_val, cell, is_member)
    sealed = evaluate_cell(daily, btc_seal, cell, is_member)
    vm = validate["metrics"]
    sm = sealed["metrics"]
    same_sign = (vm["expectancy_r"] > 0) == (sm["expectancy_r"] > 0)
    econ = evaluate_econ([_econ_summary(vm), _econ_summary(sm)], _econ_summary(sm), ECON_BAR)
    seal_cost = cost_multiple(sealed["records"], 2.0)["passed"] and cost_multiple(
        sealed["records"], 3.0
    )["passed"]
    accept = practical_pass(vm) and practical_pass(sm) and same_sign and seal_cost and econ.passed
    return {
        "key": cell.key,
        "validate": vm,
        "sealed": sm,
        "econ": econ.passed,
        "econ_passed": econ.passed,
        "verdict": "paper_candidate" if accept else "negative",
    }
