import json

import tools.regime_selector.regime_selector_btc as CLI
from moonface.research.regime_selector import grid as G


class _C:
    __slots__ = ("timestamp_ms", "open", "high", "low", "close", "volume")

    def __init__(self, ts, p):
        self.timestamp_ms = ts
        self.open = self.high = self.low = self.close = p
        self.high = p * 1.01
        self.low = p * 0.99
        self.volume = 1.0


def _candles(start, end):
    # Capped at 300 bars: reversion_in_range is O(n^2) (it re-runs
    # classify_structure + rsi over the whole prefix h1[:i+1] every bar), so a
    # full multi-year window makes the staged run take minutes. The verdict is
    # deterministically "negative" under the all-risk_off synthetic macro
    # regardless of bar count, so a small fixture preserves the test's intent.
    out, px, ts = [], 100.0, start
    k = 0
    while ts < end and len(out) < 300:
        px *= 1.001 if (k // 20) % 2 == 0 else 0.999
        out.append(_C(ts, px))
        ts += 14_400_000
        k += 1
    return out


def _patch(monkeypatch):
    monkeypatch.setattr(CLI, "load_btc",
                        lambda s, e, cache_dir: _candles(s, e))
    monkeypatch.setattr(CLI, "load_macro",
                        lambda cache_dir: {"SP500": [], "VIXCLS": [], "DTWEXBGS": []})


def test_register_writes_prereg(tmp_path):
    rc = CLI.run(["--register", "--out-dir", str(tmp_path)])
    assert rc == 0
    doc = json.loads((tmp_path / "PREREGISTRATION.json").read_text())
    assert doc["n_trials"] == 4
    assert doc["grid"] == ["R1-switch", "R1-wait", "R3-switch", "R3-wait"]
    assert doc["windows"]["sealed"] == [G.SEALED_START, G.SEALED_END]


def test_full_staged_run_reaches_a_verdict(tmp_path, monkeypatch):
    _patch(monkeypatch)
    out = str(tmp_path)
    assert CLI.run(["--register", "--out-dir", out]) == 0
    assert CLI.run(["--explore", "--out-dir", out, "--cache-dir", "x"]) == 0
    assert CLI.run(["--select", "--out-dir", out, "--cache-dir", "x"]) == 0
    assert CLI.run(["--validate", "--out-dir", out, "--cache-dir", "x"]) == 0
    result = json.loads((tmp_path / "RESULT.json").read_text())
    assert result["verdict"] in ("paper_accept", "negative")
    # all-risk_off synthetic macro: expected NEGATIVE (no risk-on trend trades)
    assert result["verdict"] == "negative"
    lead = json.loads((tmp_path / "explore_leaderboard.json").read_text())
    assert len(lead["cells"]) == 4
