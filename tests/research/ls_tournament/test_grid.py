from moonface.core.models import Candle
from moonface.research.ls_tournament.evaluate import run_explore
from moonface.research.ls_tournament.grid import TIMEFRAMES, all_configs, configs_for


def _series(n, tf_ms=7_200_000):
    out, px = [], 1000.0
    for k in range(n):
        px = px * 1.0008 + (20 if k % 15 == 0 else -3 if k % 17 == 0 else 0)
        out.append(Candle(timestamp_ms=k * tf_ms, open=px - 2, high=px + 4,
                          low=px - 4, close=px, volume=1.0))
    return out


def test_frozen_grid_count_and_group_shape():
    cfgs = all_configs(TIMEFRAMES)
    assert len(cfgs) == 120
    assert all(len(configs_for(tf)) == 60 for tf in TIMEFRAMES)

    groups: dict[str, list] = {}
    for cfg in cfgs:
        groups.setdefault(cfg.group, []).append(cfg)

    assert all(len(members) == 3 for members in groups.values())
    fams = {cfg.long_rule["family"] for cfg in cfgs}
    for required in (
        "donchian_break", "atr_channel_break", "ma_cross", "price_vs_ma",
        "roc_sign", "reversion_in_range", "vol_expansion",
        "vol_compression_breakout",
    ):
        assert required in fams

    filters = {f["name"] for cfg in cfgs for f in cfg.filters}
    for required in ("slow_ma_regime", "atr_band", "funding_extreme",
                     "oi_momentum", "macro_regime"):
        assert required in filters


def test_explore_reports_leg_and_twin_metrics():
    rows = run_explore(all_configs(["2h"]), {"2h": _series(500)})
    assert len(rows) == 60
    row = rows[0]
    for key in ("metrics", "long_rule", "short_rule", "filters", "dsr"):
        assert key in row
    assert "twin_total_r" in row["metrics"]
    assert "long_expectancy_r" in row["metrics"]
    assert row["metrics"]["trade_count"] >= 0
