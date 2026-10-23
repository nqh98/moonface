# tests/test_btcspec_search_cli.py
import json

import tools.btcspec.btcspec_search as cli
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _series(n, tf_ms):
    out, px = [], 1000.0
    for k in range(n):
        px *= 1.001 if (k // 25) % 2 == 0 else 0.999
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px * 1.01,
                          low=px * 0.99, close=px, volume=1.0))
    return out


def _patch_data(monkeypatch):
    data = {"2h": _series(2000, 7_200_000), "4h": _series(2000, 14_400_000)}
    monkeypatch.setattr(cli, "fetch_perp_candles",
                        lambda symbol, tf, s, e, cache: data[tf])


def test_register_writes_prereg_without_unseen_data(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    rc = cli.main(["--register", "--start-ms", "0", "--end-ms", "1",
                   "--out-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "PREREGISTRATION.md").exists()


def test_explore_then_select_then_validate_flow(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    base = ["--start-ms", "0", "--end-ms", "1", "--out-dir", str(tmp_path)]
    assert cli.main(["--explore"] + base) == 0
    assert (tmp_path / "explore_leaderboard.json").exists()
    assert cli.main(["--select"] + base) == 0
    frozen = json.loads((tmp_path / "frozen_candidates.json").read_text())
    assert isinstance(frozen, list)
    assert cli.main(["--validate"] + base) == 0
    assert (tmp_path / "RESULT.md").exists()
    assert (tmp_path / "result.json").exists()


def test_validate_without_frozen_returns_error(tmp_path, monkeypatch):
    _patch_data(monkeypatch)
    rc = cli.main(["--validate", "--start-ms", "0", "--end-ms", "1",
                   "--out-dir", str(tmp_path)])
    assert rc == 3


def test_split_is_55_25_20():
    xs = list(range(100))
    e, v, s = cli._split_55_25_20(xs)
    assert (len(e), len(v), len(s)) == (55, 25, 20)
