# tests/research/test_edge_search.py
from moonface.core.models import Candle
from moonface.research import edge_search as es
from moonface.kernel.econ import ECON_BAR


def _c(ts, o, h, lo, c):
    return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=c, volume=1.0)


def _ramp(n, step=10.0, atr_room=5.0):
    """Monotone up series: every bar closes `step` higher; range gives ATR>0."""
    out = []
    px = 1000.0
    for k in range(n):
        out.append(_c(k * 3_600_000, px, px + atr_room, px - atr_room, px))
        px += step
    return out


def _always_long(candles, params):
    # one LONG entry per bar in the usable middle (skip warmup + horizon tail)
    return [(i, "LONG") for i in range(params["warmup"], len(candles) - params["tail"])]


def test_prescreen_detects_strong_gross_drift(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    candles = _ramp(240)  # 240 bars: ~34 non-overlapping h=6 events (>= MIN_EVENTS=30)
    r = es.prescreen(candles, "_t", {"warmup": 20, "tail": 20}, h=6, atr_period=14)
    assert r["n"] >= es.MIN_EVENTS
    assert r["mean_ret_r"] > 0
    assert r["z"] >= es.Z_FLOOR
    assert r["passed"] is True


def test_prescreen_kills_no_drift(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    # flat-with-noise: alternating up/down closes -> ~zero mean, |z| small.
    # 240 bars => ~34 non-overlapping h=6 events (>= MIN_EVENTS), so the kill is
    # driven by |z|<Z_FLOOR — this exercises the z-gate, NOT just the n-gate.
    candles = []
    px = 1000.0
    for k in range(240):
        nxt = px + (7.0 if k % 2 == 0 else -7.0)
        candles.append(_c(k * 3_600_000, px, max(px, nxt) + 3, min(px, nxt) - 3, nxt))
        px = nxt
    r = es.prescreen(candles, "_t", {"warmup": 20, "tail": 20}, h=6, atr_period=14)
    assert r["n"] >= es.MIN_EVENTS        # kill is NOT from the n-gate
    assert r["passed"] is False           # ... it is from the z-gate:
    assert abs(r["z"]) < es.Z_FLOOR


def test_oos_dsr_passes_on_clean_uptrend(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    candles = _ramp(480)  # 480 bars: ~37 non-overlapping h=12 trades (>= MIN_EVENTS)
    exit_params = {"atr_period": 14, "k_trail": 2.0, "max_bars": 12}
    rs = es.net_trade_rs(candles, "_t", {"warmup": 20, "tail": 20},
                         "atr_trail", exit_params, h=12)
    assert len(rs) >= es.MIN_EVENTS
    d = es.oos_dsr(candles, "_t", {"warmup": 20, "tail": 20},
                   "atr_trail", exit_params, h=12, trial_srs=[], n_trials=es.TOTAL_CELLS)
    assert d["dsr"] >= es.DSR_FLOOR
    assert d["passed"] is True


def test_oos_dsr_rejects_noise(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    candles = []  # zig-zag: trades net ~0 after costs -> low Sharpe -> dsr below floor.
    # 480 bars => ~37 non-overlapping h=12 trades (>= MIN_EVENTS), so the rejection is
    # Sharpe-driven, not the n<30 gate.
    px = 1000.0
    for k in range(480):
        nxt = px + (9.0 if k % 2 == 0 else -9.0)
        candles.append(_c(k * 3_600_000, px, max(px, nxt) + 4, min(px, nxt) - 4, nxt))
        px = nxt
    exit_params = {"atr_period": 14, "k_trail": 2.0, "max_bars": 12}
    d = es.oos_dsr(candles, "_t", {"warmup": 20, "tail": 20},
                   "atr_trail", exit_params, h=12, trial_srs=[], n_trials=es.TOTAL_CELLS)
    assert d["passed"] is False
    assert d["dsr"] < es.DSR_FLOOR


def test_econ_walk_forward_passes_strong_trend(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    # uptrend with one realistic bear patch (bars 160-205): a non-zero drawdown so
    # MAR is well-defined. A pure monotone ramp has dd=0 -> _mar() returns 0.0 ->
    # fails the MAR floor; real series always have drawdown.
    candles = []
    px = 1000.0
    for k in range(400):
        step = -7.0 if 160 <= k < 205 else 10.0
        candles.append(_c(k * 3_600_000, px, px + 6, px - 6, px))
        px += step
    exit_params = {"atr_period": 14, "k_trail": 2.0, "max_bars": 12}
    r = es.econ_walk_forward(candles, "_t", {"warmup": 20, "tail": 20},
                             "atr_trail", exit_params, h=12,
                             test_bars=80, step_bars=80)
    assert r["n_windows"] >= 2
    assert r["passed"] is True
    assert r["metrics"]["profit_factor"] >= ECON_BAR.profit_factor
    assert r["metrics"]["mar"] >= ECON_BAR.mar_floor  # MAR gate exercised (dd>0)


def test_econ_walk_forward_fails_choppy(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    candles = []  # chop: longs bleed costs every trade -> bar not met
    px = 1000.0
    for k in range(400):
        nxt = px + (6.0 if k % 2 == 0 else -6.0)
        candles.append(_c(k * 3_600_000, px, max(px, nxt) + 3, min(px, nxt) - 3, nxt))
        px = nxt
    exit_params = {"atr_period": 14, "k_trail": 2.0, "max_bars": 12}
    r = es.econ_walk_forward(candles, "_t", {"warmup": 20, "tail": 20},
                             "atr_trail", exit_params, h=12,
                             test_bars=80, step_bars=80)
    assert r["passed"] is False
    assert r["reasons"]  # at least one threshold reason recorded


def test_run_cell_edge_on_strong_trend(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    # uptrend with one bear patch (bars 160-205): non-zero drawdown so stage-3 MAR is
    # well-defined; 520 bars so train_oos (440) yields >=30 non-overlapping h=12 events
    # for stages 1-2 (a pure _ramp(400)/full[:320] gives n=24<30 AND zero drawdown).
    full = []
    px = 1000.0
    for k in range(520):
        step = -7.0 if 160 <= k < 205 else 10.0
        full.append(_c(k * 3_600_000, px, px + 6, px - 6, px))
        px += step
    train_oos = full[:440]  # holdout = last 80 bars, sealed until stage 3
    cell = es.Cell(label="trend_t", family="_t",
                   params={"warmup": 20, "tail": 20},
                   exit_name="atr_trail",
                   exit_params={"atr_period": 14, "k_trail": 2.0, "max_bars": 12},
                   h=12, test_bars=80, step_bars=80, is_retest=False)
    row = es.run_cell(cell, train_oos, full, trial_srs=[], n_trials=es.TOTAL_CELLS)
    assert row["stage1"]["passed"] is True
    assert row["stage2"]["passed"] is True
    assert row["stage3"]["passed"] is True
    assert row["verdict"] == "edge"


def test_run_cell_kills_at_stage1(monkeypatch):
    monkeypatch.setitem(es.PRICE_FAMILIES, "_t", _always_long)
    flat = []
    px = 1000.0
    for k in range(400):
        nxt = px + (5.0 if k % 2 == 0 else -5.0)
        flat.append(_c(k * 3_600_000, px, max(px, nxt) + 2, min(px, nxt) - 2, nxt))
        px = nxt
    cell = es.Cell(label="trend_t", family="_t",
                   params={"warmup": 20, "tail": 20}, exit_name="atr_trail",
                   exit_params={"atr_period": 14, "k_trail": 2.0, "max_bars": 12},
                   h=12, test_bars=80, step_bars=80, is_retest=False)
    row = es.run_cell(cell, flat[:320], flat, trial_srs=[], n_trials=es.TOTAL_CELLS)
    assert row["stage1"]["passed"] is False
    assert row["stage2"] is None and row["stage3"] is None
    assert row["verdict"] == "negative"


def test_candle_csv_roundtrip_schema(tmp_path):
    """Cached 15m candles reload with identical fields + chronological order."""
    from moonface.data.ohlcv import OhlcvCache
    cache = OhlcvCache(str(tmp_path))
    candles = _ramp(50)
    cache.save("BTCUSDT", "15m", candles)
    back = cache.load("BTCUSDT", "15m")
    assert [c.timestamp_ms for c in back] == sorted(
        c.timestamp_ms for c in back
    )
    assert back[0].close == candles[0].close
    assert len(back) == len(candles)


def test_registered_cells_match_total():
    from moonface.research import edge_cells
    swing = edge_cells.cells_for("4h")
    day = edge_cells.cells_for("15m")
    assert len(swing) == 4
    assert len(day) == 5
    assert len(swing) + len(day) == es.TOTAL_CELLS
    assert all(c.family in es.PRICE_FAMILIES for c in swing + day)
    assert len({c.label for c in swing}) == len(swing)  # swing labels unique within 4h
    assert len({c.label for c in day}) == len(day)


def test_render_and_leaderboard_shapes():
    rows = [{
        "label": "donchian_break_n40", "family": "donchian_break",
        "is_retest": True,
        "stage1": {"n": 80, "z": 1.1, "passed": False, "reason": "x"},
        "stage2": None, "stage3": None, "verdict": "negative",
    }]
    lb = es.to_leaderboard(rows)
    assert lb[0]["label"] == "donchian_break_n40"
    assert lb[0]["dsr"] is None and lb[0]["verdict"] == "negative"
    md = es.render_result("4h", rows, asof="2026-06-19T00:00:00Z", data_sha="abcd")
    assert "Verdict" in md and "donchian_break_n40" in md and "abcd" in md
