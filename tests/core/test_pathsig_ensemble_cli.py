# tests/test_pathsig_ensemble_cli.py
import json
import sys
from pathlib import Path

from moonface.core.models import Candle

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import tools.engine.path_signal as path_signal  # noqa: E402

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_ensemble_writes_results_json(tmp_path):
    rung0 = tmp_path / "rung0.json"
    rung0.write_text(json.dumps({"rows": [
        {"family": "x", "params": {}, "h": 6, "status": "ok",
         "fixed_cap": {"total_r": 5.0, "max_drawdown_r": -3.0, "within_cap": True},
         "risk_adjusted": {"sharpe": 0.1, "dsr": 0.0, "mar": 0.2}}]}))
    out = tmp_path / "rung1.json"
    path_signal.ensemble(str(out), cache_dir=".backtest_cache", n_folds=2,
                         horizons=[6], rung0_path=str(rung0),
                         readers=_readers(500), pool_symbols=["ETHUSDT"])
    doc = json.loads(out.read_text())
    assert doc["config"]["horizons"] == [6]
    assert doc["rung1"] and doc["verdict"]
    assert "beats_rung0" in doc["verdict"][0]
