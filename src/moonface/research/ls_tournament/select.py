"""Train-stage selection for the BTC long/short tournament."""
from __future__ import annotations

from moonface.core.metrics import COST_FRACTION, summarize_r
from moonface.research import system_battery as sb
from moonface.research.ls_tournament.explore import _evaluate_records, _slice_context
from moonface.research.ls_tournament.grid import ExploreConfig
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR

RECENT_FRAC = 0.2
EXTRA_COST = 0.0005


def _practical_checks(metrics: dict) -> dict:
    checks = {
        "net_r_pos": metrics["total_r"] > 0,
        "expectancy_pos": metrics["expectancy_r"] > 0,
        "profit_factor": metrics["profit_factor"] >= PF_FLOOR,
        "drawdown": abs(metrics["max_drawdown_r"]) <= MAX_DD_R,
        "trade_count": metrics["trade_count"] >= MIN_TRADES,
    }
    return {"checks": checks, "passed": all(checks.values())}


def _cost_stress(records: list[dict], extra_cost: float = EXTRA_COST) -> dict:
    stressed = [r["net_r"] - extra_cost / r["atr_frac"] if r["atr_frac"] > 0 else r["net_r"]
                for r in records]
    s = summarize_r(stressed)
    return {"expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "passed": s.expectancy_r > 0 and s.profit_factor > 1.0}


def _cost_multiple(records: list[dict], mult: float) -> dict:
    """Multiplicative cost stress: charge `mult`x the modelled round-trip cost.

    The base cost (COST_FRACTION) is already inside each record's net_r, so an
    EXTRA (mult-1)*COST_FRACTION reaches a total of mult x cost. Mirrors
    practical_full's sb.cost_multiple_ok, applied to the long/short records.
    """
    return _cost_stress(records, extra_cost=(mult - 1.0) * COST_FRACTION)


def _recent_ok(candles, config: ExploreConfig, context=None, recent_frac: float = RECENT_FRAC) -> dict:
    recent_bars = max(1, int(recent_frac * len(candles)))
    recent = candles[-recent_bars:]
    ctx = _slice_context(context, len(candles) - recent_bars, len(candles))
    scored = _evaluate_records(recent, config, ctx)
    metrics = scored["metrics"]
    return {"expectancy_r": metrics["expectancy_r"], "trade_count": metrics["trade_count"],
            "passed": metrics["trade_count"] > 0 and metrics["expectancy_r"] > 0}


def _train_score(candles, config: ExploreConfig, context=None) -> dict:
    scored = _evaluate_records(candles, config, context)
    metrics = scored["metrics"]
    twin = metrics["total_r"] > metrics["twin_total_r"]
    records = scored["records"]
    selection_checks = {
        "cost_stress": _cost_stress(records)["passed"],
        "cost_2x": _cost_multiple(records, 2.0)["passed"],
        "cost_3x": _cost_multiple(records, 3.0)["passed"],
        "outlier": sb.outlier_dependence_ok([r["net_r"] for r in records], 0.05)["passed"],
        "recent": _recent_ok(candles, config, context)["passed"],
        "twin_beats": twin,
    }
    return {"scored": scored, "selection_checks": selection_checks}


def select(explore_rows, train_by_tf, context_by_tf: dict | None = None) -> list[dict]:
    by_group: dict[str, list] = {}
    for r in explore_rows:
        by_group.setdefault(r["group"], []).append(r)

    survivors: list[dict] = []
    for row in explore_rows:
        config = ExploreConfig(
            label=row["label"], timeframe=row["timeframe"],
            long_rule=row["long_rule"], short_rule=row["short_rule"],
            filters=tuple(row["filters"]), exit_name=row["exit_name"],
            exit_params=row["exit_params"], h=row["h"], group=row["group"],
            axis=row["axis"],
        )
        candles = train_by_tf[row["timeframe"]]
        ctx = None if context_by_tf is None else context_by_tf.get(row["timeframe"])
        scored = _train_score(candles, config, ctx)
        metrics = scored["scored"]["metrics"]
        core = _practical_checks(metrics)
        if not core["passed"]:
            continue
        members = sorted(by_group[row["group"]], key=lambda r: r["axis"])
        idx = next(i for i, r in enumerate(members) if r["label"] == row["label"])
        island = False
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(members) and members[j]["metrics"]["profit_factor"] >= PF_FLOOR:
                island = True
                break
        if not island:
            continue
        checks = {**core["checks"], **scored["selection_checks"], "island": True}
        if all(checks.values()):
            survivors.append({
                **row,
                "selection": {"checks": checks, "passed": True},
                "train": metrics,
            })
    return survivors
