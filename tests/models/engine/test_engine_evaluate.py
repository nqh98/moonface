# tests/test_engine_evaluate.py
from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.engine import EngineResult, evaluate_engine

H = 3_600_000

# A confirmed 1W BULL macro needs ~32 weekly bars (~5500 1h candles); a GEOMETRIC
# uptrend keeps the 4h ROC strong at high prices (a linear ramp's fractional ROC
# decays to ~0 as price grows). With confirmed BULL macro the trend book clears
# the 60-pt gate: macro 20 + breakout 20 + ma_align 10 + roc 20 = 70 (tier B).
UPTREND_N = 5500          # multiple of 4 so the last 4h bar is complete
_R = 1.002                # per-1h geometric step


def _cfg(**kw):
    base = dict(enabled=True, regime_ma_fast=10, regime_ma_slow=20,
                vol_window=8, atr_period=10)
    base.update(kw)
    return EngineConfig(**base)


def _rising(n, start=100.0, step=1.0, spread=3.0):
    out, p = [], start
    for i in range(n):
        out.append(Candle(i * H, p, p + spread, p - spread, p, 1.0))
        p += step
    return out


def _geo_uptrend(n=UPTREND_N):
    out, prev = [], 100.0
    for i in range(n):
        close = 100.0 * (_R ** i)
        out.append(Candle(i * H, prev, max(prev, close) * 1.0005,
                          min(prev, close) * 0.9995, close, 1.0))
        prev = close
    return out


def bundle_with(candles):
    return DataBundle(candles=candles)


def test_insufficient_history_waits():
    res = evaluate_engine(_cfg(), bundle_with(_rising(5)), [], now_ms=0)
    assert res.signal.decision == "WAIT"
    assert res.action == "WAIT"
    assert res.decision is None                 # pre-decide WAIT carries no decision


def test_opens_long_wt_setup_in_confirmed_bull_uptrend():
    cfg = _cfg()
    res = evaluate_engine(cfg, bundle_with(_geo_uptrend()), [], now_ms=0,
                          deriv=None)
    assert res.action == "OPEN"
    assert res.signal.decision == "LONG"
    assert res.signal.tier == "engine"
    assert "no validated-edge claim" in res.signal.risk_notes
    assert res.signal.invalidation is not None
    assert res.profile == "WT"
    assert res.target is None                    # WT has no fixed target
    assert res.decision is not None
    assert res.decision.action == "SETUP"
    assert res.decision.archetype == "trend"
    assert res.decision.direction == 1


def test_manages_existing_position_via_journal():
    cfg = _cfg()
    candles = _rising(60)
    version = engine_hash(cfg)
    # v2-versioned journal says we are LONG with a stop far below -> HOLD
    entries = [{"strategy_version": version, "status": "engine",
                "action": "OPEN", "decision": "LONG",
                "entry_price": candles[-2].close, "stop": candles[-1].close - 50,
                "extreme": candles[-2].close, "atr_at_entry": 3.0,
                "fraction": 0.01, "bars_held": 0}]
    res = evaluate_engine(cfg, bundle_with(candles), entries, now_ms=0)
    assert res.action in ("HOLD", "EXIT")


def test_paused_engine_waits_when_flat():
    cfg = _cfg(drawdown_budget_r=5.0)
    version = engine_hash(cfg)
    entries = [{"strategy_version": version, "status": "engine",
                "action": "EXIT", "realized_r": -6.0, "atr_frac": 0.01,
                "fraction": 0.01, "ts_ms": 0}]
    res = evaluate_engine(cfg, bundle_with(_rising(60)), entries, now_ms=0)
    assert res.action == "WAIT"
    assert "kill" in res.signal.reason.lower() or "paused" in res.signal.reason.lower()
    assert isinstance(res, EngineResult)


def test_hard_breaker_pause_requests_human_reset():
    cfg = _cfg(drawdown_budget_r=15.0, hard_drawdown_budget_r=10.0)
    version = engine_hash(cfg)
    entries = [{"strategy_version": version, "status": "engine",
                "action": "EXIT", "realized_r": -12.0, "atr_frac": 0.01,
                "fraction": 0.01, "ts_ms": 0}]
    res = evaluate_engine(cfg, bundle_with(_rising(60)), entries, now_ms=0)
    assert res.action == "WAIT"
    assert "human reset" in res.signal.reason.lower()


def test_cooldown_after_loss_waits():
    cfg = _cfg(cooldown_bars=6)
    version = engine_hash(cfg)
    entries = [{"strategy_version": version, "status": "engine",
                "action": "EXIT", "realized_r": -1.0, "atr_frac": 0.01,
                "fraction": 0.01, "ts_ms": 0},
               {"strategy_version": version, "status": "engine",
                "action": "WAIT", "ts_ms": H}]
    res = evaluate_engine(cfg, bundle_with(_rising(60)), entries, now_ms=2 * H)
    assert res.action == "WAIT"
    assert "cooldown" in res.signal.reason.lower()


def test_v1_version_journal_entry_is_not_reconstructed():
    # a v1-schema OPEN tagged with a different strategy_version must be invisible
    # to v2 reconstruct (the engine_hash version fold isolates it).
    cfg = _cfg()
    candles = _rising(60)
    entries = [{"strategy_version": "v1_legacy_hash", "status": "engine",
                "action": "OPEN", "decision": "LONG",
                "entry_price": candles[-2].close, "stop": candles[-1].close - 50,
                "extreme": candles[-2].close, "atr_at_entry": 3.0,
                "fraction": 0.01, "bars_held": 0}]
    res = evaluate_engine(cfg, bundle_with(candles), entries, now_ms=0)
    # not managed as an open position -> a flat WAIT, not HOLD/EXIT
    assert res.action == "WAIT"


def test_deriv_none_end_to_end_never_crashes():
    cfg = _cfg()
    res = evaluate_engine(cfg, bundle_with(_rising(60)), [], now_ms=0, deriv=None)
    assert isinstance(res, EngineResult)
    assert res.signal.decision in ("LONG", "SHORT", "WAIT")
