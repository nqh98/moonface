# tests/research/btcspec/test_validate_s2.py
import inspect

from moonface.core.models import Candle
from moonface.research.btcspec.explore import WF_STEP_BARS, WF_TEST_BARS
from moonface.research.btcspec.validate import (EXTRA_COST, TRADE_FLOOR, sealed_gate,
                                                validate_all)


def _series(n, tf_ms=3_600_000):
    out, px = [], 1000.0
    for k in range(n):
        px *= 1.002 if (k // 30) % 2 == 0 else 0.999
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px * 1.02,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def _frozen(label, axis):
    return {"label": label, "timeframe": "1h", "family": "ma_cross",
            "params": {"fast": 6, "slow": 24}, "exit_name": "atr_trail",
            "exit_params": {"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
            "h": 96, "group": "g", "axis": axis}


def test_1h_constants_present_and_slice1_unchanged():
    assert WF_TEST_BARS["1h"] == 2000 and WF_STEP_BARS["1h"] == 1000
    assert WF_TEST_BARS["2h"] == 1000 and WF_TEST_BARS["4h"] == 500
    assert TRADE_FLOOR["1h"] == 60
    assert TRADE_FLOOR["2h"] == 40 and TRADE_FLOOR["4h"] == 30


def test_extra_cost_is_threaded_with_slice1_default():
    sig_g = inspect.signature(sealed_gate)
    sig_v = inspect.signature(validate_all)
    assert sig_g.parameters["extra_cost"].default == EXTRA_COST
    assert sig_v.parameters["extra_cost"].default == EXTRA_COST


def test_default_extra_cost_reproduces_explicit_value():
    cs = _series(900)
    row = _frozen("a", 1.0)
    assert sealed_gate(cs, row) == sealed_gate(cs, row, extra_cost=EXTRA_COST)


def test_validate_all_accepts_extra_cost_and_opens_one_sealed():
    frozen = [_frozen("a", 1.0), _frozen("b", 2.0)]
    rows = validate_all(frozen, {"1h": _series(1300)}, {"1h": _series(900)},
                        extra_cost=0.0010)
    assert sum(1 for r in rows if r.get("sealed") is not None) <= 1
    assert all(r["verdict"] in {"paper_accept", "rejected"} for r in rows)
