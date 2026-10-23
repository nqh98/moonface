"""Diagnostic replay for the v3 engine — DISTRIBUTION / SHAPE ONLY.

Loops decide_v3 over a candle series and tallies how the regime matrix routes
and how often each specialist fires. It computes NO returns, NO PnL, NO edge
metric of any kind: it answers "is the engine alive and routing sanely?", not
"does it make money?". Safe to run over any window without contaminating a
future holdout (nothing about forward returns is observed).

Each bar is evaluated on a bounded trailing window so a multi-year run stays
linear; the v3 indicators are all tail-bounded, so a window >= the largest
lookback yields the same routing as the full history.
"""
from __future__ import annotations

from moonface.core.models import Candle
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.decide import decide_v3
from moonface.models.engine.v3.matrix import MECHANISMS

_BANNER = ("PLUMBING DIAGNOSTIC — REGIME/MECHANISM DISTRIBUTION ONLY. "
           "NO RETURNS, NO PNL, NOT A VERDICT.")


def replay_distribution(candles: list[Candle], cfg: EngineConfigV3,
                        lookback: int = 400) -> dict:
    """Tally routing + trigger distribution over candles[lookback:]."""
    regime_dist: dict[str, int] = {}
    selected: dict[str, int] = {name: 0 for name in MECHANISMS}
    entered: dict[str, int] = {name: 0 for name in MECHANISMS}
    action = {"ENTER": 0, "WAIT": 0}
    wait = {"extreme": 0, "empty_cell": 0, "selected_no_entry": 0}
    direction = {"long": 0, "short": 0}
    q_sum = 0.0
    q_min = 1.0
    q_max = 0.0
    n = 0

    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        window = candles[max(0, i - lookback + 1): i + 1]
        d = decide_v3(window, len(window) - 1, cfg)
        n += 1
        cell = f"{d.regime.dir_state.value}/{d.regime.vol_state.value}"
        regime_dist[cell] = regime_dist.get(cell, 0) + 1

        if d.mechanism is not None:
            selected[d.mechanism] += 1

        if d.action == "ENTER":
            action["ENTER"] += 1
            entered[d.mechanism] += 1
            direction["long" if d.direction > 0 else "short"] += 1
            q = d.quality if d.quality is not None else 0.0
            q_sum += q
            q_min = min(q_min, q)
            q_max = max(q_max, q)
        else:
            action["WAIT"] += 1
            if d.mechanism is None:
                if d.regime.vol_state.value == "EXTREME":
                    wait["extreme"] += 1
                else:
                    wait["empty_cell"] += 1
            else:
                wait["selected_no_entry"] += 1

    enters = action["ENTER"]
    by_mech = {
        name: {
            "selected": selected[name],
            "entered": entered[name],
            "trigger_rate": (round(entered[name] / selected[name], 4)
                             if selected[name] else None),
        }
        for name in sorted(MECHANISMS)
    }

    warnings: list[str] = []
    if n == 0:
        warnings.append("no bars evaluated (series shorter than lookback)")
    if enters == 0:
        warnings.append("engine never entered — all WAIT (degenerate or dead)")
    if action["WAIT"] == 0:
        warnings.append("engine always entered — no discipline (degenerate)")
    if len([c for c, v in regime_dist.items() if v > 0]) < 2:
        warnings.append("only one regime observed — classifier not routing")
    for name, stats in by_mech.items():
        if stats["selected"] and not stats["entered"]:
            warnings.append(f"{name} selected but never fired")
        if stats["selected"] == 0:
            warnings.append(f"{name} never selected by any observed regime")

    return {
        "banner": _BANNER,
        "bars_evaluated": n,
        "lookback": lookback,
        "regime_distribution": dict(sorted(regime_dist.items())),
        "action": action,
        "wait_breakdown": wait,
        "by_mechanism": by_mech,
        "enter_direction": direction,
        "enter_quality": ({"min": round(q_min, 4),
                           "mean": round(q_sum / enters, 4),
                           "max": round(q_max, 4)} if enters else None),
        "enter_rate": round(enters / n, 4) if n else 0.0,
        "warnings": warnings,
    }
