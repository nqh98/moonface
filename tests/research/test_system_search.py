# tests/research/test_system_search.py
from moonface.core.models import Candle
from moonface.research import system_search as sysrch
from moonface.research import edge_search as es
from moonface.research.system_cells import SystemCell


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _ramp(n, step=10.0, room=5.0):
    out, px = [], 1000.0
    for k in range(n):
        out.append(_c(k * 3_600_000, px, px + room, px - room, px))
        px += step
    return out


def _flat_noise(n):
    out, px = [], 1000.0
    for k in range(n):
        nxt = px + (7.0 if k % 2 == 0 else -7.0)
        out.append(_c(k * 3_600_000, px, max(px, nxt) + 3, min(px, nxt) - 3, nxt))
        px = nxt
    return out


def _always_long(candles, params):
    return [(i, "LONG") for i in range(20, len(candles) - 20)]


def _cell(label, group, swept):
    return SystemCell(label=label, timeframe="4h", family="_t",
                      params={"warmup": 20, "tail": 20},
                      exit_name="atr_trail",
                      exit_params={"k_trail": 2.0, "max_bars": 48, "atr_period": 14},
                      h=12, test_bars=200, step_bars=100, group=group,
                      swept=swept, is_retest=False)


def test_gross_drift_is_non_gating(monkeypatch):
    """A cell with NULL gross drift must still reach the system-level stages
    (regression guard vs. the prior kill-at-stage-1 pipeline)."""
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    cs = _flat_noise(600)
    cell = _cell("4h:_t:s=1", "4h:_t", 1.0)
    row = sysrch.run_system_cell(cell, cs[:480], cs, trial_srs=[0.0], n_trials=1)
    # gross is recorded but did NOT short-circuit: stage2 was attempted.
    assert row["gross"] is not None
    assert row["stage2"] is not None


def test_negative_when_dsr_fails(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    cs = _flat_noise(600)
    cell = _cell("4h:_t:s=1", "4h:_t", 1.0)
    row = sysrch.run_system_cell(cell, cs[:480], cs, trial_srs=[0.0], n_trials=72)
    assert row["stage2"]["passed"] is False
    assert row["verdict"] == "negative"


def test_plateau_requires_center_plus_neighbor():
    # three rows in one group: only the center passed stage3 -> no plateau.
    def _row(label, swept, s3pass):
        return {"label": label, "group": "g", "swept": swept,
                "stage2": {"passed": True, "dsr": 0.99},
                "stage3": {"passed": s3pass}, "battery": {"passed": True},
                "verdict": "edge_pending" if s3pass else "negative"}
    rows = [_row("lo", 1.0, False), _row("mid", 2.0, True), _row("hi", 3.0, False)]
    out = {r["label"]: r for r in sysrch.finalize_plateau(rows)}
    assert out["mid"]["plateau"] is False
    assert out["mid"]["verdict"] == "inconclusive"  # no neighbor -> not edge


def test_plateau_passes_center_and_neighbor():
    def _row(label, swept, s3pass):
        return {"label": label, "group": "g", "swept": swept,
                "stage2": {"passed": True, "dsr": 0.99},
                "stage3": {"passed": s3pass}, "battery": {"passed": True},
                "verdict": "edge_pending" if s3pass else "negative"}
    rows = [_row("lo", 1.0, True), _row("mid", 2.0, True), _row("hi", 3.0, False)]
    out = {r["label"]: r for r in sysrch.finalize_plateau(rows)}
    assert out["mid"]["plateau"] is True
    assert out["mid"]["verdict"] == "edge"


def test_render_result_smoke():
    rows = sysrch.finalize_plateau([{
        "label": "4h:x", "family": "x", "timeframe": "4h", "group": "4h:x",
        "is_retest": False, "swept": 1.0,
        "gross": {"z": 0.1}, "stage2": {"passed": False, "dsr": 0.2},
        "stage3": None, "battery": None, "verdict": "negative"}])
    txt = sysrch.render_result(rows, "2026-06-20T00:00:00Z", {"4h": "abcd1234"})
    assert "NEGATIVE" in txt
    assert "4h" in txt
