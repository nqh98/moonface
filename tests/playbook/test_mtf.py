# tests/playbook/test_mtf.py
from moonface.core.models import Candle
from moonface.research.playbook.mtf import align_higher, MTFView

H = 3_600_000


def _c(ts, close=100.0):
    return Candle(ts, close, close, close, close, 0.0)


def test_align_higher_is_lookahead_free():
    # 1h bars at 0,1h,2h,3h,4h ; 4h bar opens at 0, closes at 4h
    h1 = [_c(i * H) for i in range(5)]
    h4 = [_c(0), _c(4 * H)]
    # 4h bar0 closes at 4h; h1[i] closes at (i+1)*H. Closed iff 4h <= (i+1)*H => i>=3
    k = align_higher(h1, h4, 4 * H, H)
    assert k == [0, 0, 0, 1, 1]


def test_view_prefix_never_includes_future_bar():
    h1 = [_c(i * H) for i in range(8)]
    h2 = [_c(2 * H * j) for j in range(4)]   # 2h bars open at 0,2h,4h,6h
    h4 = [_c(4 * H * j) for j in range(2)]   # 4h bars open at 0,4h
    v = MTFView.build(h1, h2, h4)
    for i in range(len(h1)):
        h1_close = h1[i].timestamp_ms + v.tf1_ms
        for c in v.h2_prefix(i):
            assert c.timestamp_ms + v.tf2_ms <= h1_close
        for c in v.h4_prefix(i):
            assert c.timestamp_ms + v.tf4_ms <= h1_close
