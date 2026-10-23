# tests/research/practical/test_pipeline.py
from moonface.research.practical import pipeline as pl


def _result(verdict):
    return {"label": "1h:atr_channel_break:k=1.0", "timeframe": "1h",
            "family": "atr_channel_break", "params": {"k": 1.0, "atr_period": 14},
            "exit_name": "atr_trail",
            "exit_params": {"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
            "h": 48, "group": "g", "axis": 1.0, "dsr": 0.3,
            "validate": {"profit_factor": 1.3, "expectancy_r": 0.1},
            "sealed": {"profit_factor": 1.25, "expectancy_r": 0.08},
            "verdict": verdict}


def test_freeze_strips_to_verbatim_config():
    frozen = pl.freeze_candidates([_result("paper_accept")])
    assert frozen[0]["params"] == {"k": 1.0, "atr_period": 14}
    assert "validate" not in frozen[0] and "dsr" not in frozen[0]


def test_render_negative_and_positive():
    neg = pl.render_result([_result("rejected")], "2026-06-21T00:00:00Z",
                           {"1h": "abc", "4h": "def"})
    assert "NEGATIVE" in neg
    pos = pl.render_result([_result("paper_accept")], "2026-06-21T00:00:00Z",
                           {"1h": "abc", "4h": "def"})
    assert "PAPER ONLY" in pos
    assert "PAPER CANDIDATE" in pos
