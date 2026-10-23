import json

import tools.practical_full.btc_practical_full as cli
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _series(n, tf_ms=14_400_000):
    out, px = [], 1000.0
    for k in range(n):
        thrust = 40.0 if k % 6 == 0 else 0.0
        px = px * 1.0008 + thrust
        out.append(Candle(timestamp_ms=k * tf_ms, open=px - 4, high=px + 8,
                          low=px - 8, close=px, volume=1.0))
    return out


def test_register_writes_prereg_without_running(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _series(80) for tf in cli.TIMEFRAMES})
    rc = cli.main(["--register", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 0
    prereg = (tmp_path / "PREREGISTRATION.md").read_text()
    assert "DSR reported" in prereg and "2x" in prereg and "3x" in prereg
    assert "60/20/20" in prereg
    assert not (tmp_path / "explore_leaderboard.json").exists()


def test_explore_select_validate_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _series(5000) for tf in cli.TIMEFRAMES})
    base = ["--out-dir", str(tmp_path), "--start-ms", "0", "--end-ms", "1"]
    assert cli.main(["--explore", *base]) == 0
    lb = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(lb) == len(cli._grid_configs())
    assert cli.main(["--select", *base]) == 0
    assert (tmp_path / "frozen_candidates.json").exists()
    assert cli.main(["--validate", *base]) == 0
    res = json.loads((tmp_path / "result.json").read_text())
    assert all("verdict" in r for r in res)


def test_validate_feasibility_fail_on_thin_tf(tmp_path, monkeypatch):
    data = {tf: _series(5000) for tf in cli.TIMEFRAMES}
    data[cli.TIMEFRAMES[0]] = _series(10)
    monkeypatch.setattr(cli, "_load_timeframes", lambda *a, **k: data)
    (tmp_path / "frozen_candidates.json").write_text("[]")
    rc = cli.main(["--validate", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 2
    assert not (tmp_path / "RESULT.md").exists()
