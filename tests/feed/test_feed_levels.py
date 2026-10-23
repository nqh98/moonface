from __future__ import annotations

from moonface.feed.levels import derive_levels
from moonface.feed.setups import Setup
from moonface.core.pivots import PivotCtx


def _long_setup():
    return Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 4.0)


def test_long_levels_use_pivots_for_tps_and_swept_level_for_stop():
    piv = PivotCtx(p=100.0, r1=104.0, s1=96.0, r2=108.0, s2=92.0, r3=112.0, s3=88.0)
    lv = derive_levels(_long_setup(), piv, 4.0)
    assert lv.entry == 100.0
    assert lv.entry_low == 99.0 and lv.entry_high == 101.0     # +/- 0.25*ATR
    assert lv.stop == 90.0 - 0.10 * 4.0                         # swept_level - buffer
    assert (lv.tp1, lv.tp2, lv.tp3) == (104.0, 108.0, 112.0)   # r1<r2<r3, all > entry
    assert 0.0 <= lv.confidence <= 1.0


def test_tps_ascending_in_r_multiples_when_no_pivots():
    lv = derive_levels(_long_setup(), None, 4.0)
    risk = lv.entry - lv.stop
    assert lv.tp1 > lv.entry > lv.stop
    assert lv.tp2 > lv.tp1 and lv.tp3 > lv.tp2
    assert abs((lv.tp1 - lv.entry) / risk - 1.0) < 1e-9
    assert abs((lv.tp2 - lv.entry) / risk - 2.0) < 1e-9
    assert abs((lv.tp3 - lv.entry) / risk - 3.0) < 1e-9


def test_short_levels_invert_sides():
    s = Setup("sweep_choch", "SHORT", 70, 100.0, 110.0, 105.0, 4.0)
    piv = PivotCtx(p=100.0, r1=104.0, s1=96.0, r2=108.0, s2=92.0, r3=112.0, s3=88.0)
    lv = derive_levels(s, piv, 4.0)
    assert lv.stop == 110.0 + 0.10 * 4.0                        # above swept level
    assert lv.tp1 < lv.entry < lv.stop
    assert (lv.tp1, lv.tp2, lv.tp3) == (96.0, 92.0, 88.0)      # s1>s2>s3, all < entry
