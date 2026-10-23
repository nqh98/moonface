"""Report assembly: sealed protection, verdict routing, JSON safety."""
import dataclasses
import json

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.repair import (
    CANDIDATES,
    build_repair_report,
    fitted_from_payload,
    fitted_payload,
)

from tests.helpers_audit import H, _walk_series

_VERDICTS = {
    "CLOSED_NEGATIVE_GATE1", "CLOSED_NEGATIVE_GATE2",
    "CLOSED_NEGATIVE_GATE3", "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
}


def test_fitted_payload_roundtrip():
    fitted = {
        "c1_tier_merge": (40, 60),
        "c2_side_vol": {("LONG", "normal"): 5, ("SHORT", "high"): 20},
        "c3_isotonic": ((40, -0.1), (70, 0.2)),
    }
    back = fitted_from_payload(fitted_payload(fitted))
    assert back["c1_tier_merge"] == (40, 60)
    assert back["c2_side_vol"][("LONG", "normal")] == 5
    assert back["c2_side_vol"][("SHORT", "high")] == 20
    assert back["c3_isotonic"] == ((40, -0.1), (70, 0.2))


def test_report_structure_and_sealed_protection():
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    report = build_repair_report(cfg, candles, 380,
                                 train_end_ts_ms=350 * H,
                                 sealed_start_ts_ms=550 * H)
    assert set(CANDIDATES) == set(report["gate1"])
    assert report["verdict"] in _VERDICTS
    assert report["label"].startswith("trend-score repair")
    if report["survivor"] is None:
        assert report["verdict"] == "CLOSED_NEGATIVE_GATE1"
        assert report["gate2"] is None and report["gate3"] is None
    json.dumps(report)
    assert report["data"]["scored_bars"] == 700 - 380
    assert report["segments"]["train"] >= 0
    assert "dropped" in report["segments"]


def test_fitting_sees_only_train_trades(monkeypatch):
    """No-lookahead: every trade handed to a fitter exited before train."""
    import moonface.models.engine.repair as repair

    seen = {}
    real = repair.fit_tier_merge

    def spy(train):
        seen["train"] = list(train)
        return real(train)

    monkeypatch.setattr(repair, "fit_tier_merge", spy)
    candles = _walk_series(700)
    cfg = dataclasses.replace(EngineConfig(), lookback_bars=400)
    repair.build_repair_report(cfg, candles, 380,
                               train_end_ts_ms=500 * H,
                               sealed_start_ts_ms=600 * H)
    assert "train" in seen
    assert all(t.exit_ts_ms < 500 * H for t in seen["train"])
