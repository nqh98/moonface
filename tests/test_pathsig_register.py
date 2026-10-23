# tests/test_pathsig_register.py
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_register_writes_frozen_registration(tmp_path):
    out = tmp_path / "registration.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "engine" / "path_signal.py"),
         "register", "--out", str(out)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reg = json.loads(out.read_text())
    assert reg["timeframe"] == "4h"
    assert reg["horizons"] == [6, 12]
    assert reg["atr_period"] == 14
    assert reg["deploy_asset"] == "BTCUSDT"
    assert reg["dsr_threshold"] == 0.95
    assert reg["lockbox_fraction"] == 0.2
    # the frozen feature list must be non-empty and stable-ordered
    assert isinstance(reg["features"], list) and len(reg["features"]) >= 10
