import json
from dataclasses import dataclass

import tools.donchian_filter.donchian_filter as cli


@dataclass
class C:
    open: float
    high: float
    low: float
    close: float
    timestamp_ms: int


def _candles(n, start_ms=1577836800000, step=14_400_000):
    out = []
    for i in range(n):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        out.append(C(open=base, high=base + 1.0, low=base - 1.0, close=base + 0.4,
                     timestamp_ms=start_ms + i * step))
    return out


def _fake_load(start_ms, end_ms, cache_dir):
    return _candles(800, start_ms=start_ms), None


def test_staged_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load", _fake_load)
    out = str(tmp_path)

    assert cli.run(["--register", "--out-dir", out]) == 0
    prereg = json.loads((tmp_path / "PREREGISTRATION.json").read_text())
    assert prereg["thresholds"] == [18, 20, 25]
    assert prereg["windows"]["sealed"] == [1740787200000, 1782300000000]

    assert cli.run(["--explore", "--out-dir", out]) == 0
    lb = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(lb["rows"]) == 3 and "base_train" in lb

    assert cli.run(["--select", "--out-dir", out]) == 0
    fc = json.loads((tmp_path / "frozen_candidate.json").read_text())
    assert "frozen" in fc

    assert cli.run(["--validate", "--out-dir", out]) == 0
    res = json.loads((tmp_path / "RESULT.json").read_text())
    assert res["verdict"] in {"IMPROVES", "NEUTRAL", "DESTROYS_INACTIVE", "negative"}
