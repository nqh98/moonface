"""Shared synthetic fixtures for the scoring-audit tests (hermetic)."""
from __future__ import annotations

import random

from moonface.core.models import Candle
from moonface.models.engine.calibration import BarRow, BookState, HypoTrade

H = 3_600_000
ALL_MODULES = (
    "m1_macro",
    "m2_breakout",
    "m2_ma_align",
    "m3_roc",
    "m4_pullback",
    "m5_funding",
    "m1_sweep",
    "m2_reclaim",
    "m3_divergence",
    "m4_fund_ct",
    "m5_oi_flush",
    "m6_stretch",
)


def _walk_series(n, seed=7, start=100.0):
    rng = random.Random(seed)
    out: list[Candle] = []
    price = start
    for i in range(n):
        drift = rng.uniform(-1.0, 1.5)
        open_ = price
        close = max(1.0, price + drift)
        high = max(open_, close) + rng.uniform(0.0, 0.8)
        low = min(open_, close) - rng.uniform(0.0, 0.8)
        out.append(Candle(i * H, open_, high, low, close, 10.0))
        price = close
    return out


def _mk_row(i, pts):
    full = {module: 0 for module in ALL_MODULES}
    full.update(pts)
    signed = sum(full[module] for module in (
        "m1_macro",
        "m2_breakout",
        "m2_ma_align",
        "m3_roc",
        "m4_pullback",
        "m5_funding",
    ))
    direction = 1 if signed > 0 else (-1 if signed < 0 else 0)
    trend = BookState(direction=direction, score=abs(signed), breadth=3,
                      policy="ALLOW")
    return BarRow(index=i, ts_ms=i * H, macro_effective="NEUTRAL",
                  vol_state="normal", regime_trend=0, trend=trend,
                  revert=BookState(0, 0, 0, None), module_points=full,
                  sweep_wick=None, decision_action="WAIT",
                  decision_direction=0, decision_score=0)


def _mk_trade(i, score, net_r, direction=1):
    return HypoTrade(entry_index=i, exit_index=i + 3, entry_ts_ms=i * H,
                     exit_ts_ms=(i + 3) * H, book="trend",
                     direction=direction, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=3,
                     exit_reason="stop")


def _fixture(n=1200, seed=2):
    """m2_breakout carries the signal; m4_pullback is pure noise; m1_macro
    anchors the direction. All trades are LONG."""
    rng = random.Random(seed)
    rows_by_index: dict[int, BarRow] = {}
    panel: list[HypoTrade] = []
    for k in range(n):
        i = k * 35
        m1 = 20
        m2 = rng.choice((0, 20))
        m4 = rng.choice((0, 0, 0, 0, 0, 1, -1))
        row = _mk_row(i, {"m1_macro": m1, "m2_breakout": m2,
                          "m4_pullback": m4})
        rows_by_index[i] = row
        net_r = round(0.05 * m2 + rng.gauss(0.0, 0.3), 4)
        panel.append(_mk_trade(i, m1 + m2 + m4, net_r))
    return panel, rows_by_index
