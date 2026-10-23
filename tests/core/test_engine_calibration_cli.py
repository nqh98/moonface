# tests/test_engine_calibration_cli.py
"""CLI wiring only — the pure report is tested in
tests/test_engine_calibration_report.py. load_bundle is monkeypatched; the
CLI never fetches in tests."""
import json
import random

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from tools.engine.engine_calibration import build_parser, run

H = 3_600_000


def _walk_series(n, seed=7, start=100.0):
    rng = random.Random(seed)
    out, price = [], start
    for i in range(n):
        drift = rng.uniform(-1.0, 1.5)
        o = price
        c = max(1.0, price + drift)
        hi = max(o, c) + rng.uniform(0.0, 0.8)
        lo = min(o, c) - rng.uniform(0.0, 0.8)
        out.append(Candle(i * H, o, hi, lo, c, 10.0))
        price = c
    return out


def test_parser_defaults():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1"])
    assert args.engine == "promotion/engine.json"
    assert args.cache_dir == ".backtest_cache"
    assert args.warmup == 6000
    assert args.out is None


def test_run_writes_report_json(tmp_path, monkeypatch, capsys):
    candles = _walk_series(560, seed=11)
    monkeypatch.setattr(
        "tools.engine.engine_calibration.load_bundle",
        lambda asset, start_ms, end_ms, cache_dir: DataBundle(candles=candles))
    cfg_path = tmp_path / "engine.json"
    cfg_path.write_text(json.dumps({"lookback_bars": 400}))
    out_path = tmp_path / "report.json"
    rc = run(["--engine", str(cfg_path), "--start-ms", "0",
              "--end-ms", str(560 * H), "--warmup", "380",
              "--out", str(out_path)])
    assert rc == 0
    report = json.loads(out_path.read_text())
    assert report["verdict"] == "UNDERPOWERED"  # tiny synthetic sample
    assert set(report["books"]) == {"trend", "mean_revert"}
    printed = json.loads(capsys.readouterr().out)
    assert printed["verdict"] == report["verdict"]
