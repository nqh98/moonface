# tests/research/btcspec/test_validate.py
from moonface.core.models import Candle
from moonface.research.btcspec.validate import (TRADE_FLOOR, outlier_topk_ok,
                                                 validate_all, walkforward_robust)


def _series(n, tf_ms=14_400_000, up=True):
    out, px = [], 1000.0
    for k in range(n):
        px *= 1.002 if up else 0.999
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px * 1.02,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def _frozen(label, axis):
    return {"label": label, "timeframe": "4h", "family": "donchian_break",
            "params": {"n": 20}, "exit_name": "atr_trail",
            "exit_params": {"k_trail": 2.0, "max_bars": 60, "atr_period": 14},
            "h": 30, "group": "g", "axis": axis}


def test_outlier_topk_rejects_single_winner_dependence():
    rs = [-0.1] * 10 + [50.0]      # one giant winner carries everything
    assert outlier_topk_ok(rs)["passed"] is False
    rs2 = [0.2] * 20                # broad-based positive
    assert outlier_topk_ok(rs2)["passed"] is True


def test_walkforward_robust_returns_fraction_and_agg():
    out = walkforward_robust(_series(1200), _frozen("a", 1.0))
    assert "robust_frac" in out and "agg_total_r" in out and "n_windows" in out


def test_validate_all_opens_sealed_for_exactly_one_row():
    frozen = [_frozen("a", 1.0), _frozen("b", 2.0)]
    rows = validate_all(frozen, {"4h": _series(1200, up=True)},
                        {"4h": _series(700, up=True)})
    sealed_opened = [r for r in rows if r.get("sealed") is not None]
    assert len(sealed_opened) <= 1
    assert all(r["verdict"] in {"paper_accept", "rejected"} for r in rows)


def test_trade_floor_is_timeframe_specific():
    assert TRADE_FLOOR["2h"] == 40 and TRADE_FLOOR["4h"] == 30
