"""Staged register/explore/select/validate pipeline (mirrors practical/playbook)."""
from __future__ import annotations

from moonface.research.portfolio.grid import FROZEN_PORTFOLIOS
from moonface.research.portfolio.operators import vote, long_short_net, vol_target, regime_switch
from moonface.research.portfolio.evaluate import portfolio_returns, summarize_portfolio
from moonface.research.portfolio.gates import (
    portfolio_dsr,
    portfolio_battery,
    ensemble_gate,
)
from moonface.research.portfolio.validate import validate_portfolio


def build_portfolio_positions(
    spec: tuple[str, str, dict],
    positions_by_comp: list[list[float]],
    asset_bar_r: list[float],
    grid_candles,
) -> list[float]:
    """Resolve a grid spec to a position series via the named operator."""
    label, op, kw = spec
    if op == "vote":
        return vote(positions_by_comp, kw["k"])
    if op == "long_short_net":
        return long_short_net(positions_by_comp)
    if op == "vol_target":
        base = (vote(positions_by_comp, "majority") if kw["base"] == "vote_majority"
                else long_short_net(positions_by_comp))
        return vol_target(base, asset_bar_r, target_vol=kw["target_vol"],
                          vol_lookback=kw["vol_lookback"])
    if op == "regime_switch":
        return regime_switch(positions_by_comp, grid_candles,
                             floor=kw["floor"], lookback=kw["lookback"])
    raise ValueError(op)


def run_explore(
    positions_by_comp: list[list[float]],
    asset_bar_r: list[float],
    grid_candles,
    trial_srs: list[float] | None = None,
) -> list[dict]:
    """Build each of the 8 portfolios, compute returns + DSR (reported, not gated).

    If *trial_srs* is None (default), the honest multiple-comparison family is
    constructed from the portfolios' own Sharpe ratios — the correct DSR reference.
    """
    rows: list[dict] = []
    for spec in FROZEN_PORTFOLIOS:
        pos = build_portfolio_positions(spec, positions_by_comp, asset_bar_r, grid_candles)
        rets = portfolio_returns(pos, asset_bar_r, grid_candles)
        rows.append({"label": spec[0], "operator": spec[1], "kw": spec[2],
                     "positions": pos, "returns": rets,
                     "metrics": summarize_portfolio(rets)})
    if trial_srs is None:
        trial_srs = [r["metrics"]["sharpe"] for r in rows]
    n_trials = len(FROZEN_PORTFOLIOS)
    for r in rows:
        r["dsr"] = portfolio_dsr(r["returns"], trial_srs, n_trials)
    return rows


def select(
    explore_rows: list[dict],
    positions_by_comp: list[list[float]],
    asset_bar_r: list[float],
    grid_candles,
    component_metrics_list: list[dict],
) -> list[dict]:
    """Apply the conjunctive battery; survivors carry verdict='negative' if they fail."""
    survivors: list[dict] = []
    for r in explore_rows:
        battery = portfolio_battery(r["returns"], r["positions"], asset_bar_r, grid_candles)
        if not battery["passed"]:
            r["verdict"] = "negative"
            continue
        r["battery"] = battery
        survivors.append(r)
    return survivors


def validate_all(
    survivors: list[dict],
    train_oos_by_label: dict[str, list[float]],
    sealed_by_label: dict[str, list[float]],
    test_bars: int,
    step_bars: int,
    component_metrics_list: list[dict],
) -> list[dict]:
    """Open the sealed tail (walk-forward) + ensemble gate.

    Controller resolution #1: the ensemble-gate reference component is the
    single best-MAR component — both MAR and MaxDD come from THAT component,
    not from two different components.
    """
    best_comp = max(
        component_metrics_list,
        key=lambda m: m["mar"],
        default={"mar": 0.0, "max_dd_r": 0.0},
    )
    ref = {"mar": best_comp["mar"], "max_dd_r": best_comp["max_dd_r"]}

    out: list[dict] = []
    for r in survivors:
        v = validate_portfolio(
            train_oos_by_label[r["label"]],
            sealed_by_label[r["label"]],
            test_bars,
            step_bars,
        )
        r["validate"] = v
        ens = ensemble_gate(r["metrics"], ref)
        r["ensemble"] = ens
        r["verdict"] = (
            "candidate" if (v["passed"] and ens["passed"]) else "inconclusive"
        )
        out.append(r)
    return out


def freeze_candidates(survivors: list[dict]) -> list[dict]:
    """Return a frozen copy of the survivor list."""
    return list(survivors)


def to_leaderboard(rows: list[dict]) -> list[dict]:
    """Sort by MAR descending."""
    return sorted(rows, key=lambda r: r["metrics"].get("mar", 0.0), reverse=True)


def render_result(rows: list[dict], asof: str, data_shas: dict) -> str:
    lines = [
        f"# Portfolio Tournament RESULT ({asof})",
        "",
        "data_shas: " + repr(data_shas),
        "",
    ]
    for r in to_leaderboard(rows):
        m = r.get("metrics", {})
        lines.append(
            f"- {r['label']}: verdict={r.get('verdict')} "
            f"MAR={m.get('mar')} MaxDD={m.get('max_dd_r')} "
            f"PF={m.get('profit_factor')} n={m.get('n')}"
        )
    return "\n".join(lines) + "\n"
