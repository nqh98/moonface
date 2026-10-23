"""Tests for consolidated_ls CLI --run (monkeypatched runner)."""
from __future__ import annotations

from tools.consolidated.consolidated_ls import main


def _fake_run(start_ms, end_ms, cache_dir):
    """Canned result for fast CLI testing."""
    return {
        "rows": [
            {
                "rank": 1,
                "lane": "test_lane",
                "key": "test_key",
                "config": {"period": 20},
                "config_source": "manual",
                "exit_name": "atr_trail",
                "current_signal": "long",
                "status": "ok",
                "expectancy_r": 0.15,
                "pf": 1.4,
                "max_dd_r": -5.0,
                "n": 100,
                "total_r": 15.0,
                "mar": 0.75,
                "error": None,
            }
        ],
        "errors": [],
        "excluded": [],
        "window": {"start_ms": start_ms, "end_ms": end_ms},
        "btc_bars": 500,
        "btc_sha": "abc123",
    }


def test_run_writes_md_and_json(tmp_path, monkeypatch):
    """Monkeypatch runner.run, invoke CLI, assert both artifacts written."""
    monkeypatch.setattr("tools.consolidated.consolidated_ls.run", _fake_run)

    main(
        [
            "--run",
            "--out-dir",
            str(tmp_path),
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--cache-dir",
            ".backtest_cache",
        ]
    )

    md = tmp_path / "LEADERBOARD.md"
    js = tmp_path / "RESULT.json"
    assert md.exists(), "LEADERBOARD.md not written"
    assert js.exists(), "RESULT.json not written"

    content = md.read_text()
    assert "DIAGNOSTIC RE-RANK" in content

    import json

    data = json.loads(js.read_text())
    assert data["evidence_class"] == "diagnostic_rerank"
