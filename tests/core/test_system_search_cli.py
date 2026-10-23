# tests/test_system_search_cli.py
import json

import tools.lanes.system_search as cli
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _ramp(n, step=10.0, room=5.0, tf_ms=4 * 3_600_000):
    out, px = [], 1000.0
    for k in range(n):
        out.append(Candle(timestamp_ms=k * tf_ms, open=px, high=px + room,
                          low=px - room, close=px, volume=1.0))
        px += step
    return out


def test_split_60_20_20():
    cs = _ramp(1000)
    train_oos, full = cli._split_60_20_20(cs)
    assert len(train_oos) == 800        # train+OOS
    assert len(full) == 1000            # holdout = last 200, inside full only
    assert train_oos == cs[:800]


def test_register_writes_prereg_without_running(tmp_path, monkeypatch):
    # register must not call fetch for a run; it may sha cached data if present.
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _ramp(50) for tf in cli.TIMEFRAMES})
    rc = cli.main(["--register", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1", "--cache-dir", "x"])
    assert rc == 0
    prereg = (tmp_path / "PREREGISTRATION.md").read_text()
    assert "n_trials" in prereg
    assert "72" in prereg                # pooled cell count
    assert "60/20/20" in prereg or "60 / 20 / 20" in prereg
    assert not (tmp_path / "RESULT.md").exists()


def test_run_writes_result_and_leaderboard(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_load_timeframes",
                        lambda *a, **k: {tf: _ramp(4000) for tf in cli.TIMEFRAMES})
    rc = cli.main(["--run", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 0
    assert (tmp_path / "RESULT.md").exists()
    lb = json.loads((tmp_path / "leaderboard.json").read_text())
    assert len(lb) == 72                 # every cell appears
    assert all("verdict" in row for row in lb)


def test_run_feasibility_fail_on_thin_timeframe(tmp_path, monkeypatch):
    # one timeframe too short to split -> feasibility fail (rc==2), no RESULT.
    data = {tf: _ramp(4000) for tf in cli.TIMEFRAMES}
    data["15m"] = _ramp(5)
    monkeypatch.setattr(cli, "_load_timeframes", lambda *a, **k: data)
    rc = cli.main(["--run", "--out-dir", str(tmp_path),
                   "--start-ms", "0", "--end-ms", "1"])
    assert rc == 2
    assert not (tmp_path / "RESULT.md").exists()
