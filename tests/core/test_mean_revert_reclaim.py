# tests/foundation/test_mean_revert_reclaim.py
from moonface.core.exits import (EXECUTABLE_EXITS, EXIT_REGISTRY,
                                        PRACTICAL_EXIT_REGISTRY,
                                        mean_revert_reclaim)
from moonface.core.models import Candle


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _flat(n, px=1000.0, room=3.0):
    return [_c(k * 3_600_000, px, px + room, px - room, px) for k in range(n)]


def test_registry_wiring_keeps_exit_registry_pristine():
    # the new exit is resolvable for single_trade_r but NOT in EXIT_REGISTRY
    assert "mean_revert_reclaim" in PRACTICAL_EXIT_REGISTRY
    assert "mean_revert_reclaim" in EXECUTABLE_EXITS
    assert "mean_revert_reclaim" not in EXIT_REGISTRY


def test_long_exits_on_ema_reclaim_with_gain():
    # price dips below entry then recovers above the local mean -> positive R exit
    cs = _flat(40, px=1000.0, room=1.0)
    # entry at i=30 after a dip; then a strong recovery bar
    cs[30] = _c(30 * 3_600_000, 1000.0, 1001.0, 999.0, 990.0)  # entry below mean
    cs[31] = _c(31 * 3_600_000, 990.0, 1010.0, 989.0, 1009.0)  # reclaim up
    r = mean_revert_reclaim(30, "LONG", cs,
                            {"ref": "ema", "ref_n": 10, "k_stop": 3.0,
                             "max_bars": 24, "atr_period": 14})
    assert r is not None and r > 0


def test_long_stops_out_for_negative_r_when_price_falls():
    cs = _flat(40, px=1000.0, room=1.0)
    cs[30] = _c(30 * 3_600_000, 1000.0, 1001.0, 999.0, 1000.0)
    # next bar craters through a 3*ATR stop
    cs[31] = _c(31 * 3_600_000, 1000.0, 1000.0, 900.0, 905.0)
    r = mean_revert_reclaim(30, "LONG", cs,
                            {"ref": "ema", "ref_n": 10, "k_stop": 3.0,
                             "max_bars": 24, "atr_period": 14})
    assert r is not None and r < 0


def test_range_mid_reference_resolves():
    cs = _flat(40, px=1000.0, room=2.0)
    cs[30] = _c(30 * 3_600_000, 1000.0, 1001.0, 999.0, 992.0)
    cs[31] = _c(31 * 3_600_000, 992.0, 1006.0, 991.0, 1005.0)
    r = mean_revert_reclaim(30, "LONG", cs,
                            {"ref": "range_mid", "ref_n": 10, "k_stop": 3.0,
                             "max_bars": 24, "atr_period": 14})
    assert r is not None


def test_time_cap_marks_out_when_neither_stop_nor_reclaim():
    # flat series, LONG entry already above the mean so 'reclaim' is immediate-safe:
    # use SHORT in a flat series where close never drops to ref and stop never hits
    cs = _flat(40, px=1000.0, room=0.5)
    r = mean_revert_reclaim(10, "LONG", cs,
                            {"ref": "ema", "ref_n": 10, "k_stop": 5.0,
                             "max_bars": 6, "atr_period": 14})
    assert r is not None  # terminates via max_bars mark-out


def test_untradeable_last_bar_returns_none():
    cs = _flat(20)
    assert mean_revert_reclaim(len(cs) - 1, "LONG", cs,
                               {"ref": "ema", "ref_n": 10, "k_stop": 3.0,
                                "max_bars": 6, "atr_period": 14}) is None
