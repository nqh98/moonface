from moonface.core.models import Candle
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.validate import segment_metrics, validate_candidate

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


def _view(start, n):
    h1 = _h1([100 + (start + i) * 0.2 for i in range(n)])
    return MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))


def test_segment_metrics_shape():
    cfg = all_playbook_configs()[0]
    m = segment_metrics(_view(0, 500), cfg)
    for key in ("trade_count", "total_r", "expectancy_r", "profit_factor",
                "max_drawdown_r", "cost_stress_ok"):
        assert key in m


def test_validate_candidate_emits_verdict():
    cfg = all_playbook_configs()[0]
    out = validate_candidate(cfg, _view(0, 500), _view(500, 500))
    assert out["verdict"] in ("paper_accept", "rejected")
    assert "validate" in out and "sealed" in out
