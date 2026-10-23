from moonface.core.models import Candle
from moonface.research import system_battery as sb


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _ramp(n, step=10.0, room=5.0):
    out, px = [], 1000.0
    for k in range(n):
        out.append(_c(k * 3_600_000, px, px + room, px - room, px))
        px += step
    return out


def _always_long(candles, params):
    return [(i, "LONG") for i in range(params["warmup"], len(candles) - params["tail"])]


def test_trade_count_gate():
    assert sb.trade_count_ok([0.1] * 30, 30)["passed"] is True
    assert sb.trade_count_ok([0.1] * 29, 30)["passed"] is False


def test_outlier_dependence_detects_single_winner():
    # 40 tiny losers + one huge winner -> trimming the winner flips expectancy<0.
    rs = [-0.01] * 40 + [20.0]
    res = sb.outlier_dependence_ok(rs, 0.05)
    assert res["base_exp"] > 0
    assert res["trimmed_exp"] <= 0
    assert res["passed"] is False


def test_outlier_dependence_robust_stream_passes():
    rs = [0.2] * 50
    assert sb.outlier_dependence_ok(rs, 0.05)["passed"] is True


def test_cost_stress_kills_thin_edge(monkeypatch):
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_t", _always_long)
    cs = _ramp(480, step=10.0)
    p = {"warmup": 20, "tail": 20}
    ep = {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}
    base = sb.cost_stress_ok(cs, "_t", p, "atr_trail", ep, 12, 0.0)
    huge = sb.cost_stress_ok(cs, "_t", p, "atr_trail", ep, 12, 5.0)  # absurd cost
    assert base["passed"] is True
    assert huge["passed"] is False


def test_cost_multiple_at_1x_equals_base(monkeypatch):
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_t", _always_long)
    cs = _ramp(480, step=10.0)
    p = {"warmup": 20, "tail": 20}
    ep = {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}
    base = sb.cost_stress_ok(cs, "_t", p, "atr_trail", ep, 12, 0.0)
    one_x = sb.cost_multiple_ok(cs, "_t", p, "atr_trail", ep, 12, 1.0)
    assert one_x["expectancy_r"] == base["expectancy_r"]
    assert one_x["mult"] == 1.0


def test_cost_multiple_higher_mult_lowers_expectancy(monkeypatch):
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_t", _always_long)
    cs = _ramp(480, step=10.0)
    p = {"warmup": 20, "tail": 20}
    ep = {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}
    two_x = sb.cost_multiple_ok(cs, "_t", p, "atr_trail", ep, 12, 2.0)
    three_x = sb.cost_multiple_ok(cs, "_t", p, "atr_trail", ep, 12, 3.0)
    assert three_x["expectancy_r"] < two_x["expectancy_r"]


def test_cost_multiple_kills_thin_edge_at_3x(monkeypatch):
    # A trend ramp with a tiny per-trade edge survives 1x but should die at a
    # heavy cost multiple — same mechanism cost_stress uses, expressed as a ratio.
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_t", _always_long)
    cs = _ramp(480, step=1.0, room=80.0)  # tiny drift relative to range -> thin edge
    p = {"warmup": 20, "tail": 20}
    ep = {"k_trail": 2.0, "max_bars": 48, "atr_period": 14}
    huge = sb.cost_multiple_ok(cs, "_t", p, "atr_trail", ep, 12, 50.0)
    assert huge["passed"] is False


def test_no_lookahead_passes_for_causal_generator(monkeypatch):
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_t", _always_long)
    cs = _ramp(200)
    res = sb.no_lookahead_ok(cs, "_t", {"warmup": 20, "tail": 0}, split_k=120, margin=5)
    assert res["passed"] is True


def test_no_lookahead_fails_for_peeking_generator(monkeypatch):
    def _peek(candles, params):
        # references the LAST bar's close -> signal set depends on the future
        thr = candles[-1].close
        return [(i, "LONG") for i in range(20, len(candles) - 1)
                if candles[i].close > thr * 0.5]
    monkeypatch.setitem(sb.PRICE_FAMILIES, "_peek", _peek)
    cs = _ramp(200)
    res = sb.no_lookahead_ok(cs, "_peek", {}, split_k=120, margin=5)
    assert res["passed"] is False
