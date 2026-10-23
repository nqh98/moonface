# tests/test_engine_honest_report.py
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from tools.engine.engine_honest_report import build_report

H = 3_600_000


def _cfg(**kw):
    base = dict(enabled=True, regime_ma_fast=10, regime_ma_slow=20,
                vol_window=8, atr_period=10)
    base.update(kw)
    return EngineConfig(**base)


def _rise_then_crash(n_up=120, n_down=40):
    out, p = [], 100.0
    for i in range(n_up):
        out.append(Candle(i * H, p, p + 3, p - 3, p, 1.0))
        p += 1.0
    for j in range(n_down):
        out.append(Candle((n_up + j) * H, p, p + 3, p - 3, p, 1.0))
        p -= 3.0
    return out


def test_report_has_verdict_blocks_and_scorecard():
    report = build_report(_cfg(), _rise_then_crash(), warmup=60)
    # the committed scorecard (core verdict)
    assert "scorecard" in report
    assert "net_r" in report["scorecard"]
    assert "state" in report["scorecard"]
    # the three framing-correction blocks
    for block in ("recency", "outlier_dependence", "cost_sensitivity"):
        assert block in report, block
    for seg in ("full", "first_half", "second_half", "last_365d"):
        assert seg in report["recency"], seg
    assert "net_r_ex_best3" in report["outlier_dependence"]
    assert "net_r_3x" in report["cost_sensitivity"]
    # provenance: faithful window recorded
    assert report["rolling_window_bars"] == _cfg().lookback_bars


def test_report_net_r_reconciles_across_blocks():
    report = build_report(_cfg(), _rise_then_crash(), warmup=60)
    net = report["scorecard"]["net_r"]
    assert report["recency"]["full"]["net_r"] == net
    assert report["cost_sensitivity"]["net_r_1x"] == net
    assert report["outlier_dependence"]["net_r"] == net
