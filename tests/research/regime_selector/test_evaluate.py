from moonface.research.regime_selector import evaluate as E


def test_beats_controls_requires_strictly_greater_than_both():
    cell = {"net_r": 10.0, "trailing_365d_net_r": 5.0}
    lo = {"net_r": 4.0, "trailing_365d_net_r": 1.0}
    hi = {"net_r": 9.0, "trailing_365d_net_r": 4.0}
    r = E.beats_controls(cell, lo, hi)
    assert r["beats_net"] and r["beats_recent"] and r["beats_both"]
    # tie on net vs one control -> not strictly greater
    r2 = E.beats_controls({"net_r": 9.0, "trailing_365d_net_r": 5.0}, lo, hi)
    assert not r2["beats_net"] and not r2["beats_both"]


def test_beats_controls_net_only_mode():
    cell = {"net_r": 10.0, "trailing_365d_net_r": 0.0}
    a = {"net_r": 1.0, "trailing_365d_net_r": 99.0}
    b = {"net_r": 2.0, "trailing_365d_net_r": 99.0}
    r = E.beats_controls(cell, a, b, recent=False)
    assert r["beats_net"] and r["beats_both"]
    assert "beats_recent" not in r


def test_cell_vector_has_cost_stress_block(monkeypatch):
    # stub selector_rt: 1x=[+2], 2x=[+1], 3x=[0] over one trade at exit_ts=t
    def fake_selector_rt(candles, macro, reg, act, cost_mult=1.0):
        return [(1000, {1.0: 2.0, 2.0: 1.0, 3.0: 0.0}[cost_mult])]

    monkeypatch.setattr(E, "selector_rt", fake_selector_rt)
    v = E.cell_vector([], {}, object(), "switch", 0, 10_000)
    assert v["cost_stress"] == {"net_r_1x": 2.0, "net_r_2x": 1.0, "net_r_3x": 0.0}
    assert v["net_r"] == 2.0
    assert v["trades"] == 1
