import json

import tools.ls_tournament.ls_tournament as cli
from moonface.core.models import Candle


def _series(n, tf_ms=7_200_000):
    out, px = [], 1000.0
    for k in range(n):
        px = px * 1.0008 + (20 if k % 15 == 0 else -3 if k % 17 == 0 else 0)
        out.append(Candle(timestamp_ms=k * tf_ms, open=px - 2, high=px + 4,
                          low=px - 4, close=px, volume=1.0))
    return out


def _patch(monkeypatch):
    data = {tf: _series(600) for tf in cli.TIMEFRAMES}
    monkeypatch.setattr(cli, "_load_timeframes", lambda *a, **k: data)
    monkeypatch.setattr(cli, "_load_context", lambda *a, **k: {})


def test_staged_cli_smoke(tmp_path, monkeypatch):
    _patch(monkeypatch)
    out = str(tmp_path)

    assert cli.run(["--register", "--out-dir", out, "--symbol", "BTCUSDT",
                    "--start-ms", "0", "--end-ms", "1"]) == 0
    prereg = json.loads((tmp_path / "PREREGISTRATION.json").read_text())
    assert prereg["n_trials"] == 120
    assert len(prereg["grid"]) == 120

    assert cli.run(["--explore", "--out-dir", out, "--symbol", "BTCUSDT",
                    "--start-ms", "0", "--end-ms", "1"]) == 0
    lead = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(lead) == 120

    assert cli.run(["--select", "--out-dir", out, "--symbol", "BTCUSDT",
                    "--start-ms", "0", "--end-ms", "1"]) == 0
    frozen = json.loads((tmp_path / "frozen_candidates.json").read_text())
    assert isinstance(frozen, list)

    assert cli.run(["--validate", "--out-dir", out, "--symbol", "BTCUSDT",
                    "--start-ms", "0", "--end-ms", "1"]) == 0
    result = json.loads((tmp_path / "RESULT.json").read_text())
    assert result["verdict"] in {"paper_candidate", "negative"}
    assert (tmp_path / "FINDINGS.md").exists()


def test_validate_without_frozen_returns_three(tmp_path, monkeypatch):
    _patch(monkeypatch)
    rc = cli.run(["--validate", "--out-dir", str(tmp_path), "--symbol", "BTCUSDT",
                  "--start-ms", "0", "--end-ms", "1"])
    assert rc == 3

