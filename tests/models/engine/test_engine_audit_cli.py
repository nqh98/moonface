"""Audit CLI: stage routing, mechanical-failure exits, report file.

Hermetic: load_bundle and the deriv builder are monkeypatched.
"""
import json

from moonface.core.bundle import DataBundle
from moonface.models.engine.deriv import DerivSnapshot
from moonface.models.engine.deriv_history import DerivCoverage
import tools.engine.engine_audit as cli

from tests.helpers_audit import H, _walk_series

import pytest

pytestmark = pytest.mark.slow


def _patch_bundle(monkeypatch, n=700):
    candles = _walk_series(n)
    monkeypatch.setattr(
        cli,
        "load_bundle",
        lambda *a, **kw: DataBundle(candles=candles),
    )
    return candles


def _base_args(tmp_path, stage="1"):
    return [
        "--stage", stage,
        "--start-ms", "0",
        "--end-ms", str(700 * H),
        "--warmup", "380",
        "--engine", "promotion/engine.json",
        "--lookback-bars", "400",
        "--out", str(tmp_path / "report.json"),
    ]


def test_stage1_writes_report(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    assert cli.run(_base_args(tmp_path)) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["stage"] == 1
    assert report["deriv"] is None
    assert set(report["books"]) == {"trend", "mean_revert"}


def test_truncated_data_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch, n=100)
    assert cli.run(_base_args(tmp_path)) == 2
    assert not (tmp_path / "report.json").exists()


def test_stage2_coverage_below_floor_exits_2(monkeypatch, tmp_path):
    _patch_bundle(monkeypatch)
    monkeypatch.setattr(
        cli,
        "build_deriv_by_index",
        lambda *a, **kw: ({}, DerivCoverage(320, 320, 100)),
    )
    assert cli.run(_base_args(tmp_path, stage="2")) == 2
    assert not (tmp_path / "report.json").exists()


def test_stage2_coverage_ok_runs_and_records_meta(monkeypatch, tmp_path):
    candles = _patch_bundle(monkeypatch)
    snaps = {
        j: DerivSnapshot(funding_pct=50.0, oi_change_6h=0.0)
        for j in range(380, len(candles))
    }
    monkeypatch.setattr(
        cli,
        "build_deriv_by_index",
        lambda *a, **kw: (snaps, DerivCoverage(320, 320, 318)),
    )
    assert cli.run(_base_args(tmp_path, stage="2")) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["stage"] == 2
    assert report["deriv"]["funding_coverage"] == 1.0
    assert report["deriv"]["coverage_floor"] == 0.90
