from moonface.core.models import Candle
from moonface.research.practical import select as sel


def _row(label, group, axis, pf, exp=0.1, dd=-5.0, trades=50, total=5.0):
    return {"label": label, "group": group, "axis": axis, "timeframe": "1h",
            "family": "atr_channel_break", "exit_name": "atr_trail",
            "params": {"k": 1.0, "atr_period": 14},
            "exit_params": {"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
            "h": 48, "dsr": 0.1,
            "metrics": {"trade_count": trades, "total_r": total,
                        "expectancy_r": exp, "profit_factor": pf,
                        "max_drawdown_r": dd, "robust_frac": 0.7,
                        "n_windows": 3, "sharpe": 0.1}}


def test_passes_core_rejects_thin_or_drawn_down():
    assert sel.passes_core(_row("x", "g", 1.0, pf=1.3)["metrics"])["passed"]
    assert not sel.passes_core(_row("x", "g", 1.0, pf=1.05)["metrics"])["passed"]
    assert not sel.passes_core(_row("x", "g", 1.0, pf=1.3, dd=-40.0)["metrics"])["passed"]
    assert not sel.passes_core(_row("x", "g", 1.0, pf=1.3, trades=10)["metrics"])["passed"]
    assert not sel.passes_core(_row("x", "g", 1.0, pf=1.3, exp=-0.1, total=-5.0)["metrics"])["passed"]


def test_island_requires_passing_neighbor():
    rows = [_row("lo", "g", 1.0, pf=1.05), _row("mid", "g", 2.0, pf=1.3),
            _row("hi", "g", 3.0, pf=1.05)]
    by_group = {"g": rows}
    assert sel.island_ok(rows[1], by_group) is False   # lone spike
    rows2 = [_row("lo", "g", 1.0, pf=1.2), _row("mid", "g", 2.0, pf=1.3),
             _row("hi", "g", 3.0, pf=1.05)]
    by_group2 = {"g": rows2}
    assert sel.island_ok(rows2[1], by_group2) is True  # neighbor passes


def test_select_end_to_end_keeps_only_clean_survivors():
    # a real explore set: a ramp where atr_channel_break trends profitably
    from moonface.research.practical.families import configs_for
    from moonface.research.practical.explore import run_explore

    def _ramp(n, step=6.0, room=4.0):
        out, px = [], 1000.0
        for k in range(n):
            out.append(Candle(timestamp_ms=k * 3_600_000, open=px, high=px + room,
                              low=px - room, close=px, volume=1.0))
            px += step
        return out
    cs = _ramp(1500)
    cfgs = [c for c in configs_for("1h") if c.family == "atr_channel_break"]
    rows = run_explore(cfgs, {"1h": cs})
    survivors = sel.select(rows, {"1h": cs})
    assert all(r["selection"]["passed"] for r in survivors)
    assert len(survivors) <= len(rows)
