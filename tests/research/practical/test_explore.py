from moonface.core.models import Candle
from moonface.research.practical import explore as ex
from moonface.research.practical.families import ExploreConfig


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _ramp(n, step=5.0, room=4.0, tf_ms=3_600_000):
    out, px = [], 1000.0
    for k in range(n):
        out.append(_c(k * tf_ms, px, px + room, px - room, px))
        px += step
    return out


def _cfg(label, group, axis, family="atr_channel_break"):
    return ExploreConfig(
        label=label, timeframe="1h", family=family,
        params={"k": 1.0, "atr_period": 14} if family == "atr_channel_break"
        else {"period": 14, "low": 25, "high": 75},
        exit_name="atr_trail",
        exit_params={"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
        h=48, group=group, axis=axis)


def test_walk_forward_bars_cover_all_supported_timeframes():
    # the practical-full lane runs 2h; WF window sizing must exist for it.
    for tf in ("1h", "2h", "4h"):
        assert tf in ex.WF_TEST_BARS and tf in ex.WF_STEP_BARS
        assert ex.WF_TEST_BARS[tf] > ex.WF_STEP_BARS[tf] > 0


def test_evaluate_config_reports_full_metric_block():
    cs = _ramp(1500)
    m = ex.evaluate_config(cs, "atr_channel_break",
                           {"k": 1.0, "atr_period": 14}, "atr_trail",
                           {"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
                           48, ex.WF_TEST_BARS["1h"], ex.WF_STEP_BARS["1h"])
    for key in ("trade_count", "total_r", "expectancy_r", "profit_factor",
                "max_drawdown_r", "robust_frac", "n_windows", "sharpe", "rs"):
        assert key in m


def test_run_explore_reports_dsr_without_gating():
    cs = _ramp(1500)
    cfgs = [_cfg("a", "g", 1.0), _cfg("b", "g", 1.5), _cfg("c", "g", 2.0)]
    rows = ex.run_explore(cfgs, {"1h": cs})
    assert len(rows) == 3
    for r in rows:
        assert "dsr" in r and isinstance(r["dsr"], float)
        assert "metrics" in r and "profit_factor" in r["metrics"]
    # sorted by dsr desc
    assert rows == sorted(rows, key=lambda r: r["dsr"], reverse=True)
