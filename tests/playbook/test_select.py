from moonface.core.models import Candle
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.explore import run_explore
from moonface.research.playbook.select import select, playbook_cost_stress_ok

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


def _view(n=600):
    h1 = _h1([100 + i * 0.2 for i in range(n)])
    return MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))


def test_select_returns_only_passing_configs():
    configs = all_playbook_configs()
    view = _view()
    rows = run_explore(configs, view)
    by_label = {c.label: c for c in configs}
    survivors = select(rows, view, by_label)
    assert isinstance(survivors, list)
    for s in survivors:
        assert s["selection"]["passed"] is True


def test_cost_stress_returns_passed_flag():
    cfg = all_playbook_configs()[0]
    out = playbook_cost_stress_ok(_view(), cfg)
    assert "passed" in out and "expectancy_r" in out
