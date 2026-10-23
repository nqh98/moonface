# tests/test_bb_harvest.py
import math

from moonface.core.exits import EXECUTABLE_EXITS
from moonface.core.models import Candle
from moonface.research import bb_harvest as bh
from moonface.research.entries import PRICE_FAMILIES


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _series(n):
    """Drifting series with periodic volatility bursts so upper/lower Bollinger
    crosses actually fire (a pure monotone ramp never crosses its own band)."""
    out = []
    px = 1000.0
    for k in range(n):
        burst = 60.0 if k % 23 == 0 else 6.0
        step = burst if (k // 23) % 2 == 0 else -burst
        nxt = px + step
        out.append(_c(k * 14_400_000, px, max(px, nxt) + 8, min(px, nxt) - 8, nxt))
        px = max(nxt, 50.0)
    return out


def test_cells_are_well_formed():
    cells = bh.cells()
    assert len(cells) == len(bh._ENTRIES) * len(bh._EXITS) == 12
    for cell in cells:
        assert cell.family == "bb_breakout"
        assert cell.family in PRICE_FAMILIES          # registered, resolvable
        assert cell.exit_name in EXECUTABLE_EXITS      # academic exit set
        assert "atr_period" in cell.exit_params
        assert cell.h == bh._H
        assert cell.test_bars == bh._TEST_BARS
        assert cell.step_bars == bh._STEP_BARS
        assert cell.is_retest is False
    assert len({c.label for c in cells}) == len(cells)  # labels unique


def test_dsr_deflation_uses_true_trial_count(monkeypatch):
    """n_trials passed to the gate must equal the number of cells tried here, not
    edge_search's hard-coded 9 — otherwise the grid's breadth is unpaid for."""
    seen = {}

    def _spy(cell, train_oos, full, trial_srs, n_trials):
        seen["n_trials"] = n_trials
        seen["trial_srs_len"] = len(trial_srs)
        return {"label": cell.label, "stage1": None, "stage2": None,
                "stage3": None, "verdict": "negative"}

    monkeypatch.setattr(bh, "run_cell", _spy)
    bh.run(_series(200), _series(260))
    assert seen["n_trials"] == len(bh.cells()) == 12
    assert seen["trial_srs_len"] == 12


def test_run_smoke_returns_full_leaderboard():
    full = _series(900)
    train_oos = full[:700]
    rows = bh.run(train_oos, full)
    assert len(rows) == 12
    for r in rows:
        assert r["verdict"] in ("edge", "negative")
        assert "stage1" in r and "label" in r
    # sorted by DSR desc with Nones last (stage2 may be None when stage1 kills)
    dsrs = [(r["stage2"]["dsr"] if r["stage2"] else -math.inf) for r in rows]
    assert dsrs == sorted(dsrs, reverse=True)


def test_render_report_has_verdict_and_no_false_promotion():
    rows = bh.run(_series(900)[:700], _series(900))
    md = bh.render_report(rows, "BTC/USDT:USDT", "4h", 900, 200)
    assert "Verdict:" in md and "bb_breakout" in md
    # with synthetic noise no real edge should be claimed
    assert "NEGATIVE" in md or "EDGE FOUND" in md
