# tests/playbook/test_pipeline.py
from moonface.research.playbook.pipeline import freeze_survivors, render_result


def test_freeze_keeps_only_labels():
    rows = [{"label": "slope10:don20:atr_trail", "selection": {"passed": True}}]
    assert freeze_survivors(rows) == ["slope10:don20:atr_trail"]


def test_render_negative_when_no_accept():
    rows = [{"label": "x", "verdict": "rejected",
             "validate": {"profit_factor": 1.0, "expectancy_r": -0.1},
             "sealed": {"profit_factor": 0.9, "expectancy_r": -0.2}}]
    out = render_result(rows, "2026-06-22T00:00:00Z", {"1h": "abc", "4h": "def"})
    assert "NEGATIVE" in out
    assert "Donchian" in out      # isolation caveat present
