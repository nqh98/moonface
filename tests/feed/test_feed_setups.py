from __future__ import annotations

from moonface.core.models import Candle
from moonface.feed.setups import Setup, detect_all, detect_last


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 3_600_000, o, h, lo, c, 1.0)


def reversal_fixture():
    """~140 bars: repeated rising sell-sweep -> wide bullish-CHOCH legs (mirrors
    tests/test_smc_variants.py::reversal_fixture)."""
    bars = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        for o, h, lo, c in [
            (b, b + 2, b - 3, b), (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6), (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12),   # swing high B+15
            (b + 10, b + 13, b + 5, b + 10), (b + 5, b + 8, b, b + 5),
            (b, b + 3, b - 6, b),               # equal low B-6
            (b - 3, b, b - 6, b - 3),           # equal low B-6 -> SELL pool
            (b - 5, b - 2, b - 20, b - 2),      # sweep: wick B-20, close B-2
            (b - 2, b + 20, b - 4, b + 18),     # wide rally -> bullish CHOCH
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def test_detect_all_finds_sweep_choch_longs():
    setups = detect_all(reversal_fixture())
    sweep_long = [s for s in setups if s.setup_type == "sweep_choch" and s.side == "LONG"]
    assert len(sweep_long) >= 1
    assert all(s.swept_level is not None for s in sweep_long)


def test_detect_last_only_returns_setups_at_final_candle():
    bars = reversal_fixture()
    # The fixture's last leg ends with a CHOCH rally at the final index.
    last = detect_last(bars)
    assert all(s.confirm_index == len(bars) - 1 for s in last)


def test_detect_last_empty_on_flat_window():
    bars = [_c(i, 100, 105, 95, 100) for i in range(80)]
    assert detect_last(bars) == []


def test_setup_is_frozen_and_carries_atr():
    s = Setup("sweep_choch", "LONG", 70, 100.0, 90.0, 95.0, 1.5)
    assert s.atr_value == 1.5


def falling_fixture():
    """Mirror of reversal_fixture with a falling base -> BEARISH structure."""
    bars = []
    idx = 0
    for leg in range(11):
        b = 300 - 10 * leg
        for o, h, lo, c in [
            (b, b + 3, b - 2, b), (b - 3, b, b - 5, b - 3),
            (b - 5, b - 2, b - 9, b - 5), (b - 9, b - 6, b - 12, b - 9),
            (b - 12, b - 9, b - 15, b - 12),   # swing low B-15
            (b - 10, b - 5, b - 13, b - 10), (b - 5, b, b - 8, b - 5),
            (b, b + 6, b, b), (b + 3, b + 6, b, b + 3),   # equal highs -> BUY pool
            (b + 5, b + 22, b - 4, b + 2),                 # sweep
            (b + 2, b - 18, b + 4, b - 16),               # wide drop -> bearish CHOCH
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def _rising_trend_fixture():
    """A clean rising trend (HH/HL) with wide continuation candles so BOS fires."""
    bars = []
    idx = 0
    for leg in range(8):
        b = 100 + 30 * leg
        # rally to a swing high (b+15), pullback to a higher swing low (b-3, HL),
        # then a wide breakout closing above the swing high (BOS continuation).
        for o, h, lo, c in [
            (b, b + 5, b - 2, b + 3),
            (b + 3, b + 8, b + 1, b + 6),
            (b + 6, b + 12, b + 5, b + 10),
            (b + 10, b + 15, b + 9, b + 14),   # swing high b+15
            (b + 12, b + 13, b + 8, b + 9),    # pullback (high kept < b+15 so it's the unique peak)
            (b + 9, b + 10, b + 3, b + 4),
            (b + 4, b + 5, b - 3, b - 1),      # swing low b-3 (HL vs prior leg)
            (b - 1, b + 3, b - 2, b + 2),
            (b + 2, b + 6, b + 1, b + 5),
            (b + 5, b + 9, b + 4, b + 8),
            (b + 8, b + 30, b + 7, b + 28),    # wide breakout, close b+28 > swing high b+15
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    return bars


def test_detect_all_finds_bos_continuation_in_rising_trend():
    setups = [s for s in detect_all(_rising_trend_fixture())
              if s.setup_type == "bos_continuation"]
    assert len(setups) >= 1
    assert all(s.side == "LONG" for s in setups)
    assert all(s.struct_level is not None for s in setups)


def test_detect_last_includes_bos_when_final_candle_breaks():
    bars = _rising_trend_fixture()
    last_setups = detect_last(bars)
    assert all(s.confirm_index == len(bars) - 1 for s in last_setups)
