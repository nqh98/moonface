"""Report assembly: sealed protection, verdict routing, JSON safety."""

import json

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import VERDICTS, build_eval_report

from tests.helpers_v3 import uptrend

import pytest

pytestmark = pytest.mark.slow

CFG3 = EngineConfigV3()
CFG22 = EngineConfig()


def test_report_structure_and_sealed_protection():
    btc = uptrend(1200)
    report = build_eval_report(
        btc,
        uptrend(1200),
        uptrend(1200),
        CFG3,
        CFG22,
        warmup=400,
        lookback=400,
    )
    assert report["verdict"] in VERDICTS
    assert report["label"].startswith("v3 backtest evaluation")
    assert "fitted" in report and "gate1" in report
    if not report["gate1"]["passed"]:
        assert report["verdict"] == "CLOSED_NEGATIVE_VALIDATION"
        assert report["gate2"] is None and report["gate3"] is None
    json.dumps(report)


def test_fit_uses_only_btc_train(monkeypatch):
    import moonface.models.engine.v3.evaluate as ev

    seen = {}
    real = ev.fit_q_floors

    def spy(train, cfg):
        seen["train"] = list(train)
        return real(train, cfg)

    monkeypatch.setattr(ev, "fit_q_floors", spy)
    ev.build_eval_report(
        uptrend(1200),
        uptrend(1200),
        uptrend(1200),
        CFG3,
        CFG22,
        warmup=400,
        lookback=400,
    )
    assert "train" in seen
    assert all(t.exit_ts_ms < ev.TRAIN_END_TS_MS for t in seen["train"])
