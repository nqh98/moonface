from moonface.core.models import Candle
from moonface.research.breadth.signals import entries_from_state
from moonface.research.breadth_internal.overlap import overlapping_entries_from_state

DAY_MS = 86_400_000
H4_MS = 4 * 3_600_000


def _btc(n):
    return [Candle(i * H4_MS, 100.0, 101.0, 99.0, 100.0, 1.0) for i in range(n)]


def test_one_entry_per_active_day_next_day_available():
    btc = _btc(60)  # 60 * 4h = 10 days of bars
    # day 0 LONG, day 1 LONG, day 2 FLAT, day 3 SHORT
    state = [(0, "LONG"), (DAY_MS, "LONG"), (2 * DAY_MS, "FLAT"), (3 * DAY_MS, "SHORT")]
    entries = overlapping_entries_from_state(btc, state, h=48)
    # 3 active days -> 3 entries; FLAT day emits nothing
    assert len(entries) == 3
    sides = [s for _, s in entries]
    assert sides == ["LONG", "LONG", "SHORT"]
    # each entry's bar timestamp is >= ts + DAY_MS (next-day available, no look-ahead)
    assert btc[entries[0][0]].timestamp_ms >= 0 + DAY_MS
    assert btc[entries[2][0]].timestamp_ms >= 3 * DAY_MS + DAY_MS


def test_overlapping_strictly_more_than_transition_mapping():
    btc = _btc(200)
    # a LONG state that persists 20 consecutive days
    state = [(i * DAY_MS, "LONG") for i in range(20)]
    overlap = overlapping_entries_from_state(btc, state, h=48)
    transition = entries_from_state(btc, state, h=48)
    assert len(overlap) > len(transition)
    assert len(overlap) == 20  # one per active day


def test_no_entries_when_btc_exhausted():
    btc = _btc(3)  # only 3 bars, far before the active days
    state = [(10 * DAY_MS, "LONG")]
    assert overlapping_entries_from_state(btc, state, h=48) == []
