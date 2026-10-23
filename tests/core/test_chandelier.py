# tests/foundation/test_chandelier.py
from moonface.core.exits import (BTCSPEC_EXIT_REGISTRY, EXECUTABLE_EXITS,
                                        EXIT_REGISTRY, chandelier)
from moonface.core.models import Candle


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _flat(n, px=1000.0, room=2.0):
    return [_c(k * 3_600_000, px, px + room, px - room, px) for k in range(n)]


def test_registry_wiring_keeps_exit_registry_pristine():
    assert "chandelier" in BTCSPEC_EXIT_REGISTRY
    assert "chandelier" in EXECUTABLE_EXITS
    assert "chandelier" not in EXIT_REGISTRY
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}


def test_long_trails_up_and_stops_on_pullback_for_positive_r():
    cs = _flat(40, px=1000.0, room=1.0)
    # entry i=20, price rallies (extreme ratchets up), then pulls back through the stop
    for j in range(21, 27):
        px = 1000.0 + (j - 20) * 20.0
        cs[j] = _c(j * 3_600_000, px, px + 2.0, px - 2.0, px)
    cs[27] = _c(27 * 3_600_000, 1120.0, 1121.0, 900.0, 905.0)  # deep pullback hits trail
    r = chandelier(20, "LONG", cs, {"atr_mult": 3.0, "max_bars": 24, "atr_period": 14})
    assert r is not None and r > 0  # locked in trend gain before the stop


def test_long_marks_out_at_max_bars_when_never_stopped():
    cs = _flat(40, px=1000.0, room=0.5)
    cs[35] = _c(35 * 3_600_000, 1000.0, 1001.0, 999.0, 1010.0)  # small drift up by cap
    r = chandelier(20, "LONG", cs, {"atr_mult": 3.0, "max_bars": 5, "atr_period": 14})
    assert r is not None  # terminates at i+max_bars


def test_short_trails_down_and_stops_on_bounce():
    cs = _flat(40, px=1000.0, room=1.0)
    for j in range(21, 27):
        px = 1000.0 - (j - 20) * 20.0
        cs[j] = _c(j * 3_600_000, px, px + 2.0, px - 2.0, px)
    cs[27] = _c(27 * 3_600_000, 880.0, 1100.0, 879.0, 1095.0)  # sharp bounce hits trail
    r = chandelier(20, "SHORT", cs, {"atr_mult": 3.0, "max_bars": 24, "atr_period": 14})
    assert r is not None and r > 0


def test_no_lookahead_truncating_after_exit_is_identical():
    cs = _flat(40, px=1000.0, room=1.0)
    for j in range(21, 27):
        px = 1000.0 + (j - 20) * 20.0
        cs[j] = _c(j * 3_600_000, px, px + 2.0, px - 2.0, px)
    cs[27] = _c(27 * 3_600_000, 1120.0, 1121.0, 900.0, 905.0)
    full = chandelier(20, "LONG", cs, {"atr_mult": 3.0, "max_bars": 24, "atr_period": 14})
    trunc = chandelier(20, "LONG", cs[:29], {"atr_mult": 3.0, "max_bars": 24, "atr_period": 14})
    assert full == trunc


def test_untradeable_entry_returns_none():
    cs = _flat(5)
    assert chandelier(4, "LONG", cs, {"atr_mult": 3.0, "max_bars": 24, "atr_period": 14}) is None
