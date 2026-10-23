import json

import tools.engine.engine_ablation as cli
from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig, engine_hash

H = 3_600_000


def _cfg(tmp_path):
    path = tmp_path / "engine.json"
    path.write_text(json.dumps({
        "enabled": True,
        "regime_ma_fast": 10,
        "regime_ma_slow": 20,
        "vol_window": 8,
        "atr_period": 5,
        "lookback_bars": 400,
        "asset": {
            "exchange": "binance",
            "symbol": "BTC/USDT:USDT",
            "timeframe": "1h",
        },
    }))
    return path


def _candles(n=16, start=100.0, step=1.0):
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


def _entry(cfg, *, ts_ms, veto=True, version=None, shadow_direction=-1,
           shadow_score=80):
    return {
        "strategy_version": version or engine_hash(cfg),
        "status": "engine",
        "action": "WAIT",
        "veto": "macro BEAR vetoes TREND long" if veto else None,
        "shadow_direction": shadow_direction,
        "shadow_score": shadow_score,
        "regime_vol": "normal",
        "candle_ts_ms": ts_ms,
        "tier": None,
    }


def test_run_replays_current_version_veto_and_fetches_candles(tmp_path, monkeypatch, capsys):
    cfg_path = _cfg(tmp_path)
    journal = tmp_path / "journal.jsonl"
    cfg = EngineConfig(
        enabled=True,
        regime_ma_fast=10,
        regime_ma_slow=20,
        vol_window=8,
        atr_period=5,
        lookback_bars=400,
        asset={
            "exchange": "binance",
            "symbol": "BTC/USDT:USDT",
            "timeframe": "1h",
        },
    )
    version = engine_hash(cfg)
    journal.write_text("\n".join([
        json.dumps(_entry(cfg, ts_ms=6 * H, veto=True, version=version)),
        json.dumps(_entry(cfg, ts_ms=6 * H, veto=True, version="other")),
        json.dumps(_entry(cfg, ts_ms=6 * H, veto=False, version=version)),
    ]) + "\n")

    seen = {}

    def fake_bundle(asset, start_ms, end_ms, cache_dir):
        seen["asset"] = asset
        seen["start_ms"] = start_ms
        seen["end_ms"] = end_ms
        seen["cache_dir"] = cache_dir
        return DataBundle(candles=_candles())

    monkeypatch.setattr(cli, "_now_ms", lambda: 16 * H + 123456)
    monkeypatch.setattr(cli, "load_bundle", fake_bundle)

    rc = cli.run([
        "--engine", str(cfg_path),
        "--journal", str(journal),
        "--cache-dir", str(tmp_path / "cache"),
    ])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["engine_hash"] == version
    assert out["n_vetoed"] == 1
    assert out["counterfactual"]["replayed"] == 1
    assert out["counterfactual"]["resolved"] == 1
    assert out["counterfactual"]["rows"][0]["resolved"] is True
    assert out["families"]["macro"]["n_vetoed"] == 1
    assert out["counterfactual"]["rows"][0]["family"] == "macro"
    assert seen["asset"] == cfg.asset
    assert seen["start_ms"] == 6 * H - 60 * H
    assert seen["end_ms"] == 16 * H
    assert seen["cache_dir"] == str(tmp_path / "cache")


def test_run_skips_candle_fetch_when_no_vetoes(tmp_path, monkeypatch, capsys):
    cfg_path = _cfg(tmp_path)
    journal = tmp_path / "journal.jsonl"
    cfg = EngineConfig(
        enabled=True,
        regime_ma_fast=10,
        regime_ma_slow=20,
        vol_window=8,
        atr_period=5,
        lookback_bars=400,
        asset={
            "exchange": "binance",
            "symbol": "BTC/USDT:USDT",
            "timeframe": "1h",
        },
    )
    journal.write_text("\n".join([
        json.dumps(_entry(cfg, ts_ms=6 * H, veto=False)),
        json.dumps(_entry(cfg, ts_ms=7 * H, veto=False)),
    ]) + "\n")

    called = {"load_bundle": False}

    def fake_bundle(*args, **kwargs):
        called["load_bundle"] = True
        raise AssertionError("load_bundle should not be called when there are no vetoes")

    def fake_gate(entries, candles, cfg_):
        return {
            "engine_hash": engine_hash(cfg_),
            "n_vetoed": 0,
            "counterfactual": {
                "replayed": 0,
                "resolved": 0,
                "net_r_if_taken": 0.0,
                "gate_saved_r": 0.0,
                "rows": [],
            },
        }

    monkeypatch.setattr(cli, "load_bundle", fake_bundle)
    monkeypatch.setattr(cli, "gate_ablation", fake_gate)

    rc = cli.run([
        "--engine", str(cfg_path),
        "--journal", str(journal),
        "--cache-dir", str(tmp_path / "cache"),
    ])
    assert rc == 0
    assert called["load_bundle"] is False
    out = json.loads(capsys.readouterr().out)
    assert out["n_vetoed"] == 0
    assert out["counterfactual"]["rows"] == []
