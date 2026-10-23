# tests/research/practical/test_validate.py
from moonface.core.models import Candle
from moonface.research.practical import validate as val


def _ramp(n, step=6.0, room=4.0):
    out, px = [], 1000.0
    for k in range(n):
        out.append(Candle(timestamp_ms=k * 3_600_000, open=px, high=px + room,
                          low=px - room, close=px, volume=1.0))
        px += step
    return out


def _chop(n):
    out, px = [], 1000.0
    for k in range(n):
        nxt = px + (8.0 if k % 2 == 0 else -8.0)
        out.append(Candle(timestamp_ms=k * 3_600_000, open=px,
                          high=max(px, nxt) + 3, low=min(px, nxt) - 3,
                          close=nxt, volume=1.0))
        px = nxt
    return out


def _row():
    return {"label": "1h:atr_channel_break:k=1.0:atr_trail", "timeframe": "1h",
            "family": "atr_channel_break", "params": {"k": 1.0, "atr_period": 14},
            "exit_name": "atr_trail",
            "exit_params": {"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
            "h": 48}


def test_segment_pass_thresholds():
    good = {"trade_count": 50, "total_r": 5.0, "expectancy_r": 0.1,
            "profit_factor": 1.3, "max_drawdown_r": -5.0, "cost_stress_ok": True}
    assert val.segment_pass(good)
    assert not val.segment_pass({**good, "profit_factor": 1.05})
    assert not val.segment_pass({**good, "cost_stress_ok": False})
    assert not val.segment_pass({**good, "trade_count": 10})


def test_accept_requires_both_segments(monkeypatch):
    row = _row()
    out = val.validate_candidate(row, _ramp(1200), _ramp(1200))
    assert out["verdict"] in ("paper_accept", "rejected")
    # a trending validate but chop sealed must NOT accept
    mixed = val.validate_candidate(row, _ramp(1200), _chop(1200))
    assert mixed["verdict"] == "rejected"
