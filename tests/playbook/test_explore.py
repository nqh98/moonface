# tests/playbook/test_explore.py
from moonface.core.models import Candle
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.explore import run_explore

H = 3_600_000


def _h1(prices):
    return [Candle(i * H, p, p + 0.3, p - 0.3, p, 1.0) for i, p in enumerate(prices)]


def _resample(h1, f):
    out = []
    for k in range(0, len(h1), f):
        ch = h1[k:k + f]
        out.append(Candle(ch[0].timestamp_ms, ch[0].open, max(c.high for c in ch),
                          min(c.low for c in ch), ch[-1].close, 0.0))
    return out


def test_run_explore_reports_dsr_for_every_config():
    h1 = _h1([100 + i * 0.2 for i in range(600)])
    view = MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))
    rows = run_explore(all_playbook_configs(), view)
    assert len(rows) == len(all_playbook_configs())
    assert all("dsr" in r and 0.0 <= r["dsr"] <= 1.0 for r in rows)
    assert all("metrics" in r for r in rows)
    # sorted by dsr descending
    assert [r["dsr"] for r in rows] == sorted((r["dsr"] for r in rows), reverse=True)
