# tests/test_pathsig_htf.py
from moonface.core.models import Candle
from moonface.research.pathsig.htf import align_htf_index

H4 = 14_400_000
D1 = 86_400_000


def _bars(n, dur, start=0):
    return [Candle(timestamp_ms=start + i * dur, open=1.0, high=1.0, low=1.0,
                   close=1.0, volume=1.0) for i in range(n)]


def test_daily_bar_not_used_until_fully_closed():
    base = _bars(12, H4)          # 12 4h bars span 2 days (close at 4h..48h)
    daily = _bars(2, D1)          # day0 closes at D1=24h; day1 closes at 2*D1=48h
    idx = align_htf_index(base, daily, base_dur_ms=H4, htf_dur_ms=D1)
    # base bar 0 closes at H4 — no daily bar has closed yet
    assert idx[0] is None
    # before D1 (first 5 bars close at 4h..20h) no daily bar is usable -> no lookahead
    assert all(j is None for j in idx[:5])
    # day0 closes at D1 = 6*H4 -> first usable at the 6th 4h bar (index 5)
    assert idx[5] == 0
    # day1 closes at 2*D1 = 12*H4, exactly when the last base bar closes (<=, contemporaneous)
    assert idx[11] == 1
    # no index ever exceeds the available daily bars
    assert all(j is None or 0 <= j <= 1 for j in idx)


def test_finer_timeframe_picks_latest_closed():
    base = _bars(3, H4)                 # closes at H4, 2H4, 3H4
    hourly = _bars(12, H4 // 4)         # 1h bars
    idx = align_htf_index(base, hourly, base_dur_ms=H4, htf_dur_ms=H4 // 4)
    # base bar 0 closes at H4: latest 1h bar closing <= H4 is the one opening at
    # 3*(H4/4), index 3
    assert idx[0] == 3
    assert idx[1] == 7
