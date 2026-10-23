"""Hypothetical-trade simulator: frozen exit discipline, hand-computed.

Cost model check (frozen position._net_r): net_r = gross_r - COST_FRACTION/atr_frac,
COST_FRACTION = 0.001."""
from moonface.core.models import Candle
from moonface.models.engine.calibration import (BarRow, BookState,
                                                nonoverlapping_stream,
                                                overlapping_panel,
                                                reversal_sensitivity,
                                                simulate_entry)
from moonface.models.engine.config import EngineConfig

H = 3_600_000


def _bar(i, o, hi, lo, c):
    return Candle(i * H, o, hi, lo, c, 1.0)


def _flat(n, price=100.0, spread=2.0, start=0):
    # every bar: TR = high-low = 2*spread -> ATR = 2*spread
    return [_bar(start + i, price, price + spread, price - spread, price)
            for i in range(n)]


def _cfg(**kw):
    base = dict(atr_period=3, k_stop=2.0, k_trail=3.0, max_bars=96,
                lookback_bars=400)
    base.update(kw)
    return EngineConfig(**base)


def _row(index, book, direction, score, breadth=3, policy="ALLOW",
         vol_state="normal", sweep_wick=None, decision_action="WAIT",
         decision_direction=0):
    trend = BookState(direction if book == "trend" else 0,
                      score if book == "trend" else 0,
                      breadth if book == "trend" else 0,
                      policy if book == "trend" else None)
    revert = BookState(direction if book == "mean_revert" else 0,
                       score if book == "mean_revert" else 0,
                       breadth if book == "mean_revert" else 0,
                       policy if book == "mean_revert" else None)
    return BarRow(index=index, ts_ms=index * H, macro_effective="NEUTRAL",
                  vol_state=vol_state, regime_trend=0, trend=trend,
                  revert=revert, module_points={}, sweep_wick=sweep_wick,
                  decision_action=decision_action,
                  decision_direction=decision_direction, decision_score=score)


def test_wt_long_stop_hit_hand_computed():
    # flat 100/spread 2 -> ATR 4; entry close 100, stop 100-2*4=92.
    # bar 11 low 80 <= 92 -> exit at 92: gross (92-100)/4 = -2.0,
    # cost 0.001/(4/100) = 0.025 -> net -2.025.
    candles = _flat(11)
    candles.append(_bar(11, 100, 101, 80, 85))
    t = simulate_entry(candles, _cfg(), _row(10, "trend", 1, 65), "trend")
    assert t is not None
    assert t.exit_index == 11
    assert t.net_r == -2.025
    assert "stop" in t.exit_reason


def test_ct_long_target_hit_hand_computed():
    # CT (mean_revert book): ATR 4, no sweep wick -> stop 100-1.5*4=94,
    # target 100+2*4=108. bar 11: low 99 (no stop), high 109 -> exit 108:
    # gross (108-100)/4 = 2.0, cost 0.025 -> net 1.975.
    candles = _flat(11)
    candles.append(_bar(11, 100, 109, 99, 105))
    t = simulate_entry(candles, _cfg(), _row(10, "mean_revert", 1, 70),
                       "mean_revert")
    assert t is not None
    assert t.net_r == 1.975
    assert "target" in t.exit_reason


def test_ct_sweep_wick_sets_stop_beyond_wick():
    # sweep_wick 95 -> stop 95 - 1.5*4 = 89. bar 11 low 90 does NOT stop
    # (90 > 89); bar 12 low 88 does -> exit 89: gross (89-100)/4 = -2.75,
    # net -2.775.
    candles = _flat(11)
    candles.append(_bar(11, 100, 100, 90, 95))
    candles.append(_bar(12, 95, 96, 88, 90))
    t = simulate_entry(candles, _cfg(),
                       _row(10, "mean_revert", 1, 70, sweep_wick=95.0),
                       "mean_revert")
    assert t is not None
    assert t.exit_index == 12
    assert t.net_r == -2.775


def test_wt_short_stop_hit_hand_computed():
    # flat 100/spread 2 -> ATR 4; short entry close 100, stop 100+2*4=108.
    # bar 11 high 120 >= 108 -> exit at 108: gross (100-108)/4 = -2.0,
    # cost 0.001/(4/100) = 0.025 -> net -2.025.
    candles = _flat(11)
    candles.append(_bar(11, 100, 120, 99, 95))
    t = simulate_entry(candles, _cfg(), _row(10, "trend", -1, 65), "trend")
    assert t is not None
    assert t.exit_index == 11
    assert t.net_r == -2.025
    assert "stop" in t.exit_reason


def test_ct_short_target_hit_hand_computed():
    # CT short: ATR 4, no sweep wick -> stop 100+1.5*4=106, target 100-2*4=92.
    # bar 11: high 101 (no stop), low 91 -> exit 92: gross (100-92)/4 = 2.0,
    # cost 0.025 -> net 1.975.
    candles = _flat(11)
    candles.append(_bar(11, 100, 101, 91, 95))
    t = simulate_entry(candles, _cfg(), _row(10, "mean_revert", -1, 70),
                       "mean_revert")
    assert t is not None
    assert t.net_r == 1.975
    assert "target" in t.exit_reason


def test_incomplete_trade_returns_none():
    candles = _flat(11)  # no bars after entry at index 10
    t = simulate_entry(candles, _cfg(), _row(10, "trend", 1, 65), "trend")
    assert t is None


def test_overlapping_panel_counts_and_skips_extreme_vol():
    candles = _flat(30)
    candles.append(_bar(30, 100, 101, 80, 85))  # exit bar for all entries
    rows = [_row(10, "trend", 1, 65),
            _row(11, "trend", 1, 40, vol_state="extreme"),
            _row(12, "trend", 0, 0),          # no direction -> not an event
            _row(13, "trend", 1, 80)]
    trades, counts = overlapping_panel(candles, _cfg(), rows, "trend")
    assert counts == {"events": 2, "incomplete": 0, "skipped_extreme_vol": 1}
    assert [t.entry_index for t in trades] == [10, 13]


def test_nonoverlapping_stream_skips_while_open():
    # trade 1: entry at 10 (ATR 4, stop 92); stop-hit bar 15 (low 80). rows at
    # 11..15 must be skipped. trade 2: entry at 16 — its ATR window includes
    # bar 15's 21-point true range, so ATR=(4+21+17)/3=14 and stop=100-28=72;
    # bar 21 low 60 <= 72 exits it. row 17 is skipped while trade 2 is open.
    candles = _flat(15)
    candles.append(_bar(15, 100, 101, 80, 85))
    candles.extend(_flat(5, start=16))
    candles.append(_bar(21, 100, 101, 60, 70))
    rows = [_row(i, "trend", 1, 60 + i) for i in range(10, 18)]
    trades = nonoverlapping_stream(candles, _cfg(), rows, "trend")
    assert [t.entry_index for t in trades] == [10, 16]


def test_reversal_sensitivity_reports_triggered_subset_both_ways():
    # one triggered row (score 65 >= 60, breadth 3, ALLOW). Opposite SETUP at
    # bar 12 closes the with-reversal run earlier than the no-reversal run.
    candles = _flat(12)
    candles.append(_bar(12, 100, 101, 99, 100))
    candles.append(_bar(13, 100, 101, 80, 85))
    rows = [_row(10, "trend", 1, 65),
            _row(11, "trend", 1, 30),  # sub-threshold: not triggered
            _row(12, "trend", 1, 30, decision_action="SETUP",
                 decision_direction=-1)]
    out = reversal_sensitivity(candles, _cfg(), rows, "trend")
    assert out["triggered_events"] == 1
    assert out["no_reversal"]["n"] == 1
    assert out["with_reversal"]["n"] == 1
    # with reversal: exit at bar 12 close 100 -> gross 0, net -0.025
    assert out["with_reversal"]["net_r"] == -0.025
    # without: rides to stop 92 at bar 13 -> net -2.025
    assert out["no_reversal"]["net_r"] == -2.025
    assert out["net_r_gap"] == 2.0
