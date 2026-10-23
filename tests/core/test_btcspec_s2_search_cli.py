# tests/test_btcspec_s2_search_cli.py
import json

import tools.btcspec.btcspec_s2_search as cli
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _series(n, tf_ms=3_600_000):
    out, px = [], 1000.0
    for k in range(n):
        px *= 1.001 if (k // 25) % 2 == 0 else 0.999
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px * 1.01,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def _patch_data(monkeypatch):
    data = {"1h": _series(3000)}
    monkeypatch.setattr(cli, "fetch_perp_candles",
                        lambda symbol, tf, s, e, cache: data[tf])


def test_s2_extra_cost_is_ten_bps():
    assert cli.S2_EXTRA_COST == 0.0010


def test_register_writes_prereg_without_unseen_data(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    rc = cli.main(["--register", "--start-ms", "0", "--end-ms", "1",
                   "--out-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "PREREGISTRATION.md").exists()
    assert "Slice 2" in (tmp_path / "PREREGISTRATION.md").read_text()


def test_explore_then_select_then_validate_flow(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    base = ["--start-ms", "0", "--end-ms", "1", "--out-dir", str(tmp_path)]
    assert cli.main(["--explore"] + base) == 0
    rows = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(rows) == 264
    assert cli.main(["--select"] + base) == 0
    assert isinstance(json.loads((tmp_path / "frozen_candidates.json").read_text()), list)
    assert cli.main(["--validate"] + base) == 0
    assert (tmp_path / "RESULT.md").exists()
    assert (tmp_path / "result.json").exists()


def test_validate_without_frozen_returns_error(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    rc = cli.main(["--validate", "--start-ms", "0", "--end-ms", "1",
                   "--out-dir", str(tmp_path)])
    assert rc == 3
