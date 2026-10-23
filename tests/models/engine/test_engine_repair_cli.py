"""Repair CLI: report file, mechanical-failure exits, sealed-length guard.

Hermetic: load_bundle is monkeypatched (audit-CLI precedent).
"""
import json

from moonface.core.bundle import DataBundle
import tools.engine.engine_repair as cli

from tests.helpers_audit import H, _walk_series


def _patch_bundle(monkeypatch, n=700):
    candles = _walk_series(n)
    monkeypatch.setattr(
        cli, "load_bundle", lambda *a, **kw: DataBundle(candles=candles))
    return candles


def _base_args(tmp_path):
    return [
        "--start-ms", "0",
        "--end-ms", str(700 * H),
        "--warmup", "380",
        "--engine", "promotion/engine.json",
        "--lookback-bars", "400",
        "--train-end-ms", str(350 * H),
        "--sealed-start-ms", str(550 * H),
        "--out", str(tmp_path / "report.json"),
    ]


def test_writes_report(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    assert cli.run(_base_args(tmp_path)) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert "verdict" in report and "gate1" in report and "fitted" in report


def test_truncated_data_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch, n=100)
    assert cli.run(_base_args(tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_short_sealed_segment_exits_2_without_overrides(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    args = [
        "--start-ms", "0", "--end-ms", str(700 * H), "--warmup", "380",
        "--engine", "promotion/engine.json", "--lookback-bars", "400",
        "--out", str(tmp_path / "report.json"),
    ]
    assert cli.run(args) == 2
    assert not (tmp_path / "report.json").exists()
