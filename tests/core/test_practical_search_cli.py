# tests/test_practical_search_cli.py
import json

import tools.practical.practical_search as cli
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _ramp(n, step=6.0, room=4.0, tf_ms=3_600_000):
    out, px = [], 1000.0
    for k in range(n):
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px + room,
                          low=px - room, close=px, volume=1.0))
        px += step
    return out


def test_split_60_20_20():
    cs = _ramp(1000)
    e, v, s = cli._split_60_20_20(cs)
    assert len(e) == 600 and len(v) == 200 and len(s) == 200
    assert e == cs[:600] and v == cs[600:800] and s == cs[800:]


def test_register_writes_prereg_without_running(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _ramp(60) for tf in cli.TIMEFRAMES})
    rc = cli.main(["--register", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 0
    prereg = (tmp_path / "PREREGISTRATION.md").read_text()
    assert "n_trials" in prereg and "72" in prereg
    assert "60/20/20" in prereg or "60 / 20 / 20" in prereg
    assert not (tmp_path / "explore_leaderboard.json").exists()


def test_explore_then_select_then_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _ramp(2500) for tf in cli.TIMEFRAMES})
    base = ["--out-dir", str(tmp_path), "--start-ms", "0", "--end-ms", "1"]
    assert cli.main(["--explore", *base]) == 0
    lb = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(lb) == 72
    assert cli.main(["--select", *base]) == 0
    assert (tmp_path / "frozen_candidates.json").exists()
    assert cli.main(["--validate", *base]) == 0
    assert (tmp_path / "RESULT.md").exists()
    res = json.loads((tmp_path / "result.json").read_text())
    assert all("verdict" in r for r in res)


def test_validate_feasibility_fail_on_thin_tf(tmp_path, monkeypatch):
    data = {tf: _ramp(2500) for tf in cli.TIMEFRAMES}
    data["1h"] = _ramp(10)
    monkeypatch.setattr(cli, "_load_timeframes", lambda *a, **k: data)
    # need a frozen_candidates.json present first
    (tmp_path / "frozen_candidates.json").write_text("[]")
    rc = cli.main(["--validate", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 2
    assert not (tmp_path / "RESULT.md").exists()
