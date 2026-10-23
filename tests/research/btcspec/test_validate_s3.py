# tests/research/btcspec/test_validate_s3.py
from moonface.core.models import Candle
from moonface.research.btcspec.explore import WF_STEP_BARS, WF_TEST_BARS
from moonface.research.btcspec.validate import TRADE_FLOOR, validate_all


def _series(n, tf_ms=1_800_000):
    out, px = [], 1000.0
    for k in range(n):
        px *= 1.002 if (k // 30) % 2 == 0 else 0.999
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px * 1.02,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def _frozen(label, axis):
    return {"label": label, "timeframe": "30m", "family": "liquidity_sweep_reclaim",
            "params": {"swing_n": 16}, "exit_name": "fixed_bracket",
            "exit_params": {"k_stop": 1.0, "m_tp": 2.0, "atr_period": 14},
            "h": 48, "group": "g", "axis": axis}


def test_intraday_constants_present_and_prior_slices_unchanged():
    assert WF_TEST_BARS["15m"] == 8000 and WF_STEP_BARS["15m"] == 4000
    assert WF_TEST_BARS["30m"] == 4000 and WF_STEP_BARS["30m"] == 2000
    assert WF_TEST_BARS["1h"] == 2000 and WF_STEP_BARS["1h"] == 1000
    assert WF_TEST_BARS["2h"] == 1000 and WF_TEST_BARS["4h"] == 500
    assert TRADE_FLOOR["15m"] == 100 and TRADE_FLOOR["30m"] == 80
    assert TRADE_FLOOR["1h"] == 60
    assert TRADE_FLOOR["2h"] == 40 and TRADE_FLOOR["4h"] == 30


def test_validate_all_runs_on_30m_rows_and_opens_at_most_one_sealed():
    frozen = [_frozen("a", 1.0), _frozen("b", 2.0)]
    rows = validate_all(frozen, {"30m": _series(1300)}, {"30m": _series(900)},
                        extra_cost=0.0015)
    assert sum(1 for r in rows if r.get("sealed") is not None) <= 1
    assert all(r["verdict"] in {"paper_accept", "rejected"} for r in rows)
