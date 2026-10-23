# tests/test_engine_scorecard.py
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.scorecard import engine_scorecard


def _e(action, **kw):
    base = {"strategy_version": V, "status": "engine", "action": action}
    base.update(kw)
    return base


CFG = EngineConfig()
V = engine_hash(CFG)


def test_empty_journal():
    sc = engine_scorecard([], CFG)
    assert sc["closed_trades"] == 0
    assert sc["state"] == "active"


def test_counts_and_metrics():
    entries = [
        _e("OPEN", decision="LONG"),
        _e("HOLD", decision="LONG"),
        _e("EXIT", realized_r=2.0, atr_frac=0.01, fraction=0.01),
        _e("WAIT"),
        _e("OPEN", decision="SHORT"),
        _e("EXIT", realized_r=-1.0, atr_frac=0.01, fraction=0.01),
    ]
    sc = engine_scorecard(entries, CFG)
    assert sc["signals"] == 6
    assert sc["closed_trades"] == 2
    assert sc["net_r"] == 1.0
    assert 0.0 < sc["pct_in_position"] < 1.0
    assert sc["state"] in ("active", "cooldown", "paused")


def test_paused_state_detected():
    entries = [_e("EXIT", realized_r=-20.0, atr_frac=0.01, fraction=0.01)]
    sc = engine_scorecard(entries, EngineConfig(drawdown_budget_r=15.0))
    assert sc["state"] == "paused"


DAY_MS = 86_400_000


def test_scorecard_reports_windowed_dd_and_pause_reason():
    now = 1000 * DAY_MS
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=90.0,
                       hard_drawdown_budget_r=30.0)
    v = engine_hash(cfg)
    recent = [{"strategy_version": v, "status": "engine", "action": "EXIT",
               "realized_r": -20.0, "atr_frac": 0.01, "fraction": 0.01,
               "ts_ms": now}]
    sc = engine_scorecard(recent, cfg)
    assert sc["state"] == "paused"
    assert sc["pause_reason"] == "trailing_window"
    assert sc["windowed_drawdown_r"] == -20.0


def test_scorecard_hard_breaker_reason():
    cfg = EngineConfig(drawdown_budget_r=15.0, hard_drawdown_budget_r=10.0)
    v = engine_hash(cfg)
    entries = [{"strategy_version": v, "status": "engine", "action": "EXIT",
                "realized_r": -12.0, "atr_frac": 0.01, "fraction": 0.01,
                "ts_ms": 0}]
    sc = engine_scorecard(entries, cfg)
    assert sc["state"] == "paused"
    assert sc["pause_reason"] == "hard_breaker"


def test_scorecard_active_has_no_pause_reason():
    sc = engine_scorecard([], CFG)
    assert sc["state"] == "active"
    assert sc["pause_reason"] is None
