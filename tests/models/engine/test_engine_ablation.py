from moonface.core.models import Candle
from moonface.models.engine.ablation import veto_family
from moonface.models.engine.ablation import gate_ablation
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import (VETO_LONG_ONLY,
                                               VETO_M4_EXCLUDED,
                                               VETO_NO_CT)


H = 3_600_000


def _candles(n=24, start=100.0, step=1.0):
    out = []
    price = start
    for i in range(n):
        open_ = price
        close = price + step
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        out.append(Candle(i * H, open_, high, low, close, 1.0))
        price = close
    return out


def _entry(cfg, *, ts_ms=None, veto=True, shadow_direction=1, shadow_score=80,
           tier=None, version=None, regime_vol="normal"):
    return {
        "strategy_version": version or engine_hash(cfg),
        "status": "engine",
        "action": "WAIT",
        "veto": "macro BEAR vetoes TREND long" if veto else None,
        "shadow_direction": shadow_direction,
        "shadow_score": shadow_score,
        "regime_vol": regime_vol,
        "candle_ts_ms": ts_ms,
        "tier": tier,
    }


def test_veto_family_classifier():
    assert veto_family(None) == "none"
    assert veto_family("") == "none"
    assert veto_family("macro BEAR vetoes TREND long") == "macro"
    assert veto_family(VETO_NO_CT) == "no_ct"
    assert veto_family(VETO_LONG_ONLY) == "long_only"
    assert veto_family(VETO_M4_EXCLUDED) == "m4_pullback"
    assert veto_family("something else") == "other"


def _family_entry(ts, veto, direction, version):
    return {
        "strategy_version": version,
        "status": "engine",
        "candle_ts_ms": ts,
        "veto": veto,
        "shadow_score": 80,
        "shadow_direction": direction,
        "tier": None,
        "regime_vol": "normal",
    }


def test_gate_ablation_empty_journal_reports_zeros():
    cfg = EngineConfig()
    out = gate_ablation([], _candles(), cfg)

    assert out["engine_hash"] == engine_hash(cfg)
    assert out["n_vetoed"] == 0
    assert out["shadow_scores"] == {
        "count": 0,
        "min": None,
        "median": None,
        "max": None,
        "tier_a": 0,
        "tier_b": 0,
    }
    assert out["counterfactual"] == {
        "replayed": 0,
        "resolved": 0,
        "net_r_if_taken": 0.0,
        "gate_saved_r": 0.0,
        "rows": [],
    }
    assert isinstance(out["assumptions"], list)
    assert isinstance(out["note"], str)


def test_gate_ablation_short_veto_on_rising_series_resolves_negative_and_saves_r():
    cfg = EngineConfig(atr_period=5, max_bars=96)
    candles = _candles(16, start=100.0, step=1.0)
    out = gate_ablation([
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=-1,
               shadow_score=80, tier=None),
    ], candles, cfg)

    assert out["n_vetoed"] == 1
    assert out["counterfactual"]["replayed"] == 1
    assert out["counterfactual"]["resolved"] == 1
    assert out["counterfactual"]["rows"][0]["tier"] == "B"
    assert out["counterfactual"]["rows"][0]["shadow_direction"] == -1
    assert out["counterfactual"]["rows"][0]["resolved"] is True
    assert out["counterfactual"]["rows"][0]["net_r"] < 0
    assert out["counterfactual"]["gate_saved_r"] > 0


def test_gate_ablation_long_veto_never_exits_stays_unresolved():
    cfg = EngineConfig(atr_period=5, max_bars=96)
    candles = _candles(16, start=100.0, step=1.0)
    out = gate_ablation([
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=1,
               shadow_score=80, tier=None),
    ], candles, cfg)

    assert out["n_vetoed"] == 1
    assert out["counterfactual"]["replayed"] == 1
    assert out["counterfactual"]["resolved"] == 0
    assert out["counterfactual"]["rows"][0]["tier"] == "B"
    assert out["counterfactual"]["rows"][0]["shadow_direction"] == 1
    assert out["counterfactual"]["rows"][0]["resolved"] is False
    assert out["counterfactual"]["rows"][0]["net_r"] is None
    assert out["counterfactual"]["gate_saved_r"] == 0.0


def test_gate_ablation_missing_or_early_veto_bars_are_skipped():
    cfg = EngineConfig(atr_period=5)
    candles = _candles(16, start=100.0, step=1.0)
    out = gate_ablation([
        _entry(cfg, ts_ms=None, veto=True, shadow_direction=-1,
               shadow_score=80, tier=None),
        _entry(cfg, ts_ms=2 * H, veto=True, shadow_direction=-1,
               shadow_score=80, tier=None),
    ], candles, cfg)

    assert out["n_vetoed"] == 2
    assert out["counterfactual"]["replayed"] == 0
    assert out["counterfactual"]["resolved"] == 0
    assert len(out["counterfactual"]["rows"]) == 2
    assert out["counterfactual"]["rows"][0]["skipped"] == \
        "missing candle timestamp"
    assert out["counterfactual"]["rows"][0]["shadow_direction"] == -1
    assert out["counterfactual"]["rows"][1]["skipped"] == \
        "insufficient ATR warmup before veto bar"
    assert out["counterfactual"]["rows"][1]["shadow_direction"] == -1


def test_gate_ablation_ignores_other_versions_and_non_vetoes():
    cfg = EngineConfig(atr_period=5)
    candles = _candles(16, start=100.0, step=1.0)
    version = engine_hash(cfg)
    out = gate_ablation([
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=-1,
               shadow_score=70, tier=None, version="other"),
        _entry(cfg, ts_ms=6 * H, veto=False, shadow_direction=-1,
               shadow_score=70, tier=None, version=version),
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=-1,
               shadow_score=70, tier=None, version=version),
    ], candles, cfg)

    assert out["n_vetoed"] == 1
    assert out["shadow_scores"]["count"] == 1
    assert out["shadow_scores"]["tier_a"] == 0
    assert out["shadow_scores"]["tier_b"] == 1
    assert out["counterfactual"]["replayed"] == 1


def test_gate_ablation_skips_malformed_rows_and_continues():
    cfg = EngineConfig(atr_period=5)
    candles = _candles(16, start=100.0, step=1.0)
    out = gate_ablation([
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction="bad",
               shadow_score=80, tier=None),
        _entry(cfg, ts_ms="bad", veto=True, shadow_direction=-1,
               shadow_score=80, tier=None),
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=-1,
               shadow_score="bad", tier=None),
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=-1,
               shadow_score=80, tier=None),
    ], candles, cfg)

    assert out["n_vetoed"] == 4
    assert out["counterfactual"]["replayed"] == 1
    assert out["counterfactual"]["resolved"] == 1
    assert out["counterfactual"]["rows"][0]["skipped"] == "invalid shadow fields"
    assert out["counterfactual"]["rows"][0]["shadow_direction"] == "bad"
    assert out["counterfactual"]["rows"][1]["skipped"] == "invalid candle timestamp"
    assert out["counterfactual"]["rows"][2]["skipped"] == "invalid shadow fields"
    assert out["counterfactual"]["rows"][3]["resolved"] is True
    assert out["counterfactual"]["rows"][3]["shadow_direction"] == -1


def test_gate_ablation_skips_missing_direction():
    cfg = EngineConfig(atr_period=5)
    candles = _candles(16, start=100.0, step=1.0)
    out = gate_ablation([
        _entry(cfg, ts_ms=6 * H, veto=True, shadow_direction=None,
               shadow_score=80, tier=None),
    ], candles, cfg)

    assert out["n_vetoed"] == 1
    assert out["counterfactual"]["replayed"] == 0
    assert out["counterfactual"]["rows"][0]["skipped"] == "missing shadow fields"


def test_gate_ablation_groups_by_family():
    from moonface.models.engine.ablation import gate_ablation
    from moonface.core.models import Candle

    H = 3_600_000
    candles = [Candle(i * H, 100.0, 102.0, 98.0, 100.0, 1.0)
               for i in range(40)]
    cfg = EngineConfig(atr_period=3)
    version = engine_hash(cfg)
    ts = candles[20].timestamp_ms
    entries = [
        _family_entry(ts, "macro BEAR vetoes TREND long", 1, version),
        _family_entry(ts, VETO_NO_CT, 1, version),
        _family_entry(ts, VETO_LONG_ONLY, -1, version),
    ]

    out = gate_ablation(entries, candles, cfg)
    fams = out["families"]
    assert set(fams) == {"macro", "no_ct", "long_only"}
    for fam in fams.values():
        assert fam["n_vetoed"] == 1
        assert fam["resolved"] == 0
        assert fam["net_r_if_taken"] == 0.0
    assert all(row["family"] in ("macro", "no_ct", "long_only")
               for row in out["counterfactual"]["rows"])


def test_gate_ablation_groups_m4_family():
    cfg = EngineConfig()
    version = engine_hash(cfg)
    entries = [_family_entry(3_600_000, VETO_M4_EXCLUDED, 1, version)]
    report = gate_ablation(entries, [], cfg)
    fam = report["families"]["m4_pullback"]
    assert fam["n_vetoed"] == 1
    assert fam["shadow_scores"]["count"] == 1
