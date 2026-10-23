from moonface.core.models import Candle
from moonface.research.edge import system_signals as ss
from moonface.research.entries import PRICE_FAMILIES


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _flat(n, px=1000.0, room=2.0):
    return [_c(k * 900_000, px, px + room, px - room, px) for k in range(n)]


def test_all_four_registered():
    for k in ("vol_compression_breakout", "vol_expansion",
              "trend_pullback", "liquidity_sweep_reclaim"):
        assert k in PRICE_FAMILIES


def test_vol_compression_breakout_fires_after_squeeze():
    # 40 tight bars (small range) then a wide up-close bar -> LONG breakout.
    cs = _flat(40, room=1.0)
    px = 1000.0
    cs.append(_c(40 * 900_000, px, px + 60, px - 1, px + 55))  # expansion up
    cs.append(_c(41 * 900_000, px + 55, px + 56, px + 54, px + 55))  # tail bar
    sig = ss.vol_compression_breakout(
        cs, {"squeeze_n": 20, "atr_period": 14, "k": 1.5})
    assert any(side == "LONG" for _, side in sig)


def test_vol_expansion_fires_on_atr_surge():
    cs = _flat(40, room=1.0)
    cs.append(_c(40 * 900_000, 1000.0, 1080.0, 999.0, 1075.0))  # ATR surge, up
    cs.append(_c(41 * 900_000, 1075.0, 1076.0, 1074.0, 1075.0))
    sig = ss.vol_expansion(
        cs, {"atr_period": 14, "lookback": 20, "mult": 2.0})
    assert any(side == "LONG" for _, side in sig)


def test_trend_pullback_buys_dip_in_uptrend():
    # rising series, then a one-bar dip below MA by > pull_atr*ATR, then usable bar.
    cs = []
    px = 1000.0
    for k in range(60):
        cs.append(_c(k * 900_000, px, px + 3, px - 3, px))
        px += 5.0
    # dip bar: wick must reach BELOW the buy zone (ma_now - pull*ATR). On a 5-pt/bar
    # uptrend the lagging 30-MA sits ~75 pts under spot, so a shallow wick (px-40)
    # never probes it; use a deep wick (px-120) that closes back above the zone.
    cs.append(_c(60 * 900_000, px, px + 1, px - 120, px - 35))
    cs.append(_c(61 * 900_000, px - 35, px - 34, px - 36, px - 35))
    sig = ss.trend_pullback(
        cs, {"ma": 30, "pull_atr": 1.0, "atr_period": 14})
    assert any(side == "LONG" for _, side in sig)


def test_liquidity_sweep_reclaim_longs_failed_breakdown():
    # build a prior swing low, then a bar that wicks below it but closes back above.
    cs = _flat(30, px=1000.0, room=2.0)
    cs[15] = _c(15 * 900_000, 1000.0, 1002.0, 980.0, 1000.0)  # the swing low (980)
    cs.append(_c(30 * 900_000, 1000.0, 1001.0, 975.0, 999.0))  # sweep 980, reclaim
    cs.append(_c(31 * 900_000, 999.0, 1000.0, 998.0, 999.0))
    sig = ss.liquidity_sweep_reclaim(cs, {"swing_n": 20})
    assert any(side == "LONG" for _, side in sig)


def _sweep_reclaim_series():
    cs = _flat(30, px=1000.0, room=2.0)
    cs[15] = _c(15 * 900_000, 1000.0, 1002.0, 980.0, 1000.0)
    cs.append(_c(30 * 900_000, 1000.0, 1001.0, 975.0, 999.0))
    cs.append(_c(31 * 900_000, 999.0, 1000.0, 998.0, 999.0))
    return cs


def _uptrend_with_deep_dip():
    cs, px = [], 1000.0
    for k in range(60):
        cs.append(_c(k * 900_000, px, px + 3, px - 3, px))
        px += 5.0
    # deep wick probes the buy zone (ma_now - pull*ATR); close stays above it.
    cs.append(_c(60 * 900_000, px, px + 1, px - 120, px - 35))
    cs.append(_c(61 * 900_000, px - 35, px - 34, px - 36, px - 35))
    return cs


def test_generators_emit_no_signal_on_last_bar():
    """No generator may signal on the final bar (it has no fill bar). Each scenario is
    built to emit >=1 signal so the index check is actually exercised -- a bare _flat(30)
    emits nothing and would leave this assert vacuous."""
    scenarios = [
        (ss.vol_compression_breakout, {"squeeze_n": 20, "atr_period": 14, "k": 1.5},
         _flat(40, room=1.0) + [_c(40 * 900_000, 1000.0, 1060.0, 999.0, 1055.0),
                                _c(41 * 900_000, 1055.0, 1056.0, 1054.0, 1055.0)]),
        (ss.vol_expansion, {"atr_period": 14, "lookback": 20, "mult": 2.0},
         _flat(40, room=1.0) + [_c(40 * 900_000, 1000.0, 1080.0, 999.0, 1075.0),
                                _c(41 * 900_000, 1075.0, 1076.0, 1074.0, 1075.0)]),
        (ss.liquidity_sweep_reclaim, {"swing_n": 20}, _sweep_reclaim_series()),
        (ss.trend_pullback, {"ma": 30, "pull_atr": 1.0, "atr_period": 14},
         _uptrend_with_deep_dip()),
    ]
    for fn, params, cs in scenarios:
        sig = fn(cs, params)
        assert sig, f"{fn.__name__} emitted no signal; invariant not exercised"
        for i, _ in sig:
            assert i < len(cs) - 1, f"{fn.__name__} signaled on last bar {i}"
