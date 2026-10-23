from moonface.research.regime_selector import selector as S
from moonface.research.regime_overlay.regime import REGIME_DEFS

_REG = {r.id: r for r in REGIME_DEFS}


class _C:  # minimal candle stub the family generators + exits accept
    __slots__ = ("timestamp_ms", "open", "high", "low", "close", "volume")

    def __init__(self, ts, o, h, low, c, v=1.0):
        self.timestamp_ms = ts
        self.open, self.high, self.low, self.close, self.volume = o, h, low, c, v


def _series(n, base_ts=1577836800000, step_ms=14_400_000):
    # gently trending up so atr_channel_break/reversion_in_range both fire
    out = []
    px = 100.0
    for k in range(n):
        px *= 1.001 if (k // 20) % 2 == 0 else 0.999
        out.append(_C(base_ts + k * step_ms, px, px * 1.01, px * 0.99, px))
    return out


def test_selector_wait_is_subset_of_switch():
    candles = _series(400)
    macro = {"SP500": [], "VIXCLS": [], "DTWEXBGS": []}  # all None -> risk_off
    reg = _REG["R1"]
    wait = S.selector_rt(candles, macro, reg, "wait")
    switch = S.selector_rt(candles, macro, reg, "switch")
    # WAIT takes no risk-off trades; with all-risk_off macro it takes ZERO,
    # while SWITCH adds the MR leg -> wait ⊆ switch and len(wait) <= len(switch)
    assert len(wait) <= len(switch)
    assert set(wait).issubset(set(switch))


def test_cost_mult_reduces_net_r_monotonically():
    candles = _series(400)
    macro = {"SP500": [], "VIXCLS": [], "DTWEXBGS": []}
    reg = _REG["R1"]
    one = sum(r for _, r in S.selector_rt(candles, macro, reg, "switch", 1.0))
    three = sum(r for _, r in S.selector_rt(candles, macro, reg, "switch", 3.0))
    assert three <= one  # higher cost never increases net R


def test_control_kinds_return_sorted_streams():
    candles = _series(400)
    macro = {"SP500": [], "VIXCLS": [], "DTWEXBGS": []}
    reg = _REG["R1"]
    for kind in ("always_trend", "always_mr", "swap"):
        rt = S.control_rt(candles, macro, reg, kind)
        ts = [t for t, _ in rt]
        assert ts == sorted(ts)


def test_no_lookahead_future_macro_does_not_change_classification():
    candles = _series(400)
    reg = _REG["R1"]
    # baseline macro with history up to mid-window
    cut_ts = candles[200].timestamp_ms
    from moonface.research.exogenous.fred_data import MacroPoint  # (ts_ms, value)
    base_pts = [MacroPoint(candles[k].timestamp_ms, 100.0 + k) for k in range(0, 150)]
    macro_a = {"SP500": base_pts, "VIXCLS": [], "DTWEXBGS": []}
    # macro_b appends FAR-future points only (after cut) -> must not affect earlier trades
    future_pts = base_pts + [MacroPoint(candles[k].timestamp_ms, 9_999.0)
                             for k in range(300, 400)]
    macro_b = {"SP500": future_pts, "VIXCLS": [], "DTWEXBGS": []}
    a = [t for t in S.selector_rt(candles, macro_a, reg, "switch") if t[0] <= cut_ts]
    b = [t for t in S.selector_rt(candles, macro_b, reg, "switch") if t[0] <= cut_ts]
    assert a == b
