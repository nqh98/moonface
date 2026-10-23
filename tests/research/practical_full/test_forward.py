"""Isolated research-side forward paper-watch gate for the vol_expansion
finalist. Mirrors moonface.signal.journal.forward_report thresholds (20 trades /
12 weeks / net_r>0 / drawdown within the 0.30 budget) but accrues CLOSED forward
trades from the research replay, so it never touches promotion/ or the live
journal."""
from moonface.core.models import Candle
from moonface.research.practical_full import forward

_TF_MS = 14_400_000  # 4h


def _series(n):
    """Quiet drift bars punctuated by bullish volatility-EXPANSION thrust bars
    (range >> trailing ATR) so vol_expansion(mult=3) actually fires LONG."""
    out, px = [], 1000.0
    for k in range(n):
        if k % 7 == 0:  # expansion thrust: big range, close>open
            op = px
            px = px * 1.003 + 30
            hi, lo = px + 5, op - 5
        else:           # quiet drift bar, small range
            op = px
            px = px * 1.0003
            hi, lo = max(op, px) + 3, min(op, px) - 3
        out.append(Candle(timestamp_ms=k * _TF_MS, open=op, high=hi, low=lo,
                          close=px, volume=1.0))
    return out


_CFG = {"family": "vol_expansion",
        "params": {"mult": 3.0, "atr_period": 14, "lookback": 24},
        "exit_name": "atr_trail",
        "exit_params": {"k_trail": 2.0, "max_bars": 120, "atr_period": 14},
        "h": 24, "fraction": 0.01}


def test_only_entries_at_or_after_t0_are_counted():
    cs = _series(900)
    t0 = cs[450].timestamp_ms
    trades_all, _, _ = forward._forward_trades(cs, _CFG, 0)
    trades_fwd, _, _ = forward._forward_trades(cs, _CFG, t0)
    assert len(trades_fwd) < len(trades_all)  # pre-t0 trades excluded
    assert len(trades_fwd) > 0


def test_unresolved_edge_entries_count_as_open_not_closed():
    cs = _series(700)
    # an entry within max_bars of the data end cannot be a closed trade
    _, open_n, _ = forward._forward_trades(cs, _CFG, 0)
    assert open_n >= 1


def test_report_starts_inconclusive_with_no_forward_data():
    cs = _series(700)
    t0 = cs[-1].timestamp_ms + _TF_MS  # t0 in the future -> 0 forward trades
    rep = forward.forward_report(cs, _CFG, t0, t0)
    assert rep["closed_trades"] == 0
    assert rep["gate"]["passed"] is False
    assert rep["gate"]["min_trades"] is False


def test_gate_passes_on_clean_profitable_forward_window():
    cs = _series(1500)
    rep = forward.forward_report(cs, _CFG, 0, cs[-1].timestamp_ms)
    assert rep["closed_trades"] >= forward.FORWARD_MIN_TRADES
    assert rep["net_r"] > 0
    assert rep["elapsed_weeks"] >= forward.FORWARD_MIN_WEEKS
    assert rep["gate"]["drawdown_within_p95"] is True
    assert rep["gate"]["passed"] is True


def test_drawdown_budget_is_the_locked_030():
    assert forward.MAX_DD_BUDGET == 0.30
    assert forward.FORWARD_MIN_TRADES == 20
    assert forward.FORWARD_MIN_WEEKS == 12.0
