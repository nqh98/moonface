# tests/research/btcspec/test_explore.py
from moonface.core.models import Candle
from moonface.research.btcspec.families import configs_for
from moonface.research.btcspec.explore import run_explore


def _series(n):
    out = []
    px = 1000.0
    for k in range(n):
        px *= 1.001 if (k // 20) % 2 == 0 else 0.999
        out.append(Candle(timestamp_ms=k * 14_400_000, open=px, high=px * 1.01,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def test_run_explore_emits_row_per_config_with_reported_dsr():
    configs = [c for c in configs_for("4h") if c.family == "donchian_break"][:6]
    rows = run_explore(configs, {"4h": _series(800)})
    assert len(rows) == len(configs)
    for r in rows:
        assert "dsr" in r and "metrics" in r
        assert {"total_r", "profit_factor", "robust_frac"} <= set(r["metrics"])
    # sorted by net total_r descending (DSR never gates / reorders the gate)
    totals = [r["metrics"]["total_r"] for r in rows]
    assert totals == sorted(totals, reverse=True)


def test_run_explore_is_deterministic():
    configs = [c for c in configs_for("4h") if c.family == "ma_cross"][:4]
    data = {"4h": _series(800)}
    assert run_explore(configs, data) == run_explore(configs, data)
