"""Tests for the staged portfolio-tournament CLI (tools/portfolio/portfolio_search.py).

Only offline-safe paths are exercised:
  --register  -> exit 0 + PREREGISTRATION.md written
  --validate  -> exit 3 when frozen_candidates.json missing

Explore/select happy paths require real perp data and are human-gated.
"""
import subprocess
import sys


def _run(args, tmp_path):
    return subprocess.run(
        [sys.executable, "tools/portfolio/portfolio_search.py",
         "--symbol", "BTCUSDT", "--out-dir", str(tmp_path), *args],
        capture_output=True, text=True, timeout=120,
    )


def test_register_writes_prereg(tmp_path):
    r = _run(["--register"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "PREREGISTRATION.md").exists()
    content = (tmp_path / "PREREGISTRATION.md").read_text()
    # --register freezes the window to the module constants START_MS..END_MS
    # (1577836800000 = 2020-01-01 .. 1782000000000), NOT any CLI --start-ms.
    assert "1577836800000" in content
    assert "1782000000000" in content
    assert "Portfolio Tournament" in content


def test_validate_requires_frozen_candidates(tmp_path):
    r = _run(["--validate"], tmp_path)
    assert r.returncode == 3  # frozen_candidates.json missing -> exit 3
    assert "frozen_candidates.json" in r.stdout
