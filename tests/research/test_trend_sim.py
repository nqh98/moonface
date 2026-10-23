from moonface.core.models import Candle
from moonface.research.trend_sim import (
    TrendParams,
    detect_breakouts,
    donchian_prior,
    simulate_donchian,
)


def _candle(ts, c):
    return Candle(ts, c, c, c, c, 1.0)


def test_donchian_prior_excludes_current_bar():
    # closes 10,11,12,13,14 ; at i=3, n=2 -> bars[1,2] = 11,12 -> high 12 low 11
    cs = [_candle(i, 10 + i) for i in range(5)]
    assert donchian_prior(cs, 3, 2) == (12.0, 11.0)


def test_detect_breakouts_long_only_emits_on_close_above_prior_high():
    # strictly rising series: every bar from i=n clears the prior-n high
    cs = [_candle(i, 10 + i) for i in range(5)]
    outs = detect_breakouts(cs, n=2, long_only=True)
    assert outs == [(2, "BUY"), (3, "BUY"), (4, "BUY")]


def test_detect_breakouts_long_only_ignores_short_signals():
    # falling series: no long breakouts
    cs = [_candle(i, 20 - i) for i in range(5)]
    assert detect_breakouts(cs, n=2, long_only=True) == []


def test_detect_breakouts_symmetric_emits_short_on_close_below_prior_low():
    cs = [_candle(i, 20 - i) for i in range(5)]
    outs = detect_breakouts(cs, n=2, long_only=False)
    assert outs == [(2, "SELL"), (3, "SELL"), (4, "SELL")]


_4H = 4 * 3_600_000  # realistic bar timestamps so 8h funding prints land in holds


def _choppy_candles():
    """Flat base with spike-then-crash cycles. Each long breakout is immediately
    reversed below its ATR stop -> a stop-out loss. Several cycles -> several
    non-overlapping LOSING trades. (A trailing-stop strategy is actually
    profitable on a clean sinusoid — it harvests each oscillation — so a
    directionless *profit* is not a reliable failure; this fixture guarantees
    the stop-out path fires.)"""
    cs = []
    t = 0
    for _cycle in range(4):
        for _ in range(8):
            cs.append(Candle(t * _4H, 100, 101, 99, 100, 1.0))
            t += 1
        cs.append(Candle(t * _4H, 100, 105, 100, 104, 1.0))  # breakout (close 104 > 101)
        t += 1
        cs.append(Candle(t * _4H, 104, 104, 80, 82, 1.0))  # crash -> stop-out
        t += 1
    return cs


def _trending_up_candles(start_price=100.0, bars=80):
    """Steady uptrend. Per-bar gain (3.0) EXCEEDS the bar spread (1.0), so each
    close clears the prior-n high -> reliable long entries that ride the trend."""
    out = []
    for i in range(bars):
        p = start_price + i * 3.0
        out.append(Candle(i * _4H, p, p + 1.0, p - 1.0, p, 1.0))
    return out


def test_simulate_donchian_trending_up_produces_positive_r():
    cs = _trending_up_candles()
    params = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                         long_only=True, fee_rate=0.0, slippage=0.0)
    trades = simulate_donchian(cs, params)
    assert len(trades) >= 1
    assert sum(t.r_multiple for t in trades) > 0


def test_simulate_donchian_choppy_stops_out_at_a_loss():
    cs = _choppy_candles()
    params = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                         long_only=True, fee_rate=0.0, slippage=0.0)
    trades = simulate_donchian(cs, params)
    # The spike-then-crash cycles are designed to stop every long out at a loss
    assert len(trades) >= 1
    assert all(t.r_multiple < 0 for t in trades)
    assert sum(t.r_multiple for t in trades) <= 0


def test_simulate_donchian_no_overlap_one_open_trade_at_a_time():
    cs = _choppy_candles()  # several spike/crash cycles -> several trades
    params = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                         long_only=True, fee_rate=0.0, slippage=0.0)
    trades = simulate_donchian(cs, params)
    assert len(trades) >= 2
    for prev, cur in zip(trades, trades[1:]):
        assert cur.entry_index >= prev.exit_index   # no overlap


def test_simulate_donchian_reports_funding_zero_when_disabled():
    cs = _trending_up_candles()
    params = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                         long_only=True, fee_rate=0.0, slippage=0.0,
                         funding_enabled=False)
    trades = simulate_donchian(cs, params)
    assert all(t.funding_paid_r == 0.0 for t in trades)


def test_simulate_donchian_funding_reduces_long_r_when_positive_funding():
    cs = _trending_up_candles()
    funding = [(i * 28_800_000, 0.0010) for i in range(20)]  # +0.10% every 8h
    off = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                      long_only=True, fee_rate=0.0, slippage=0.0, funding_enabled=False)
    on = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                     long_only=True, fee_rate=0.0, slippage=0.0, funding_enabled=True)
    t_off = simulate_donchian(cs, off)
    t_on = simulate_donchian(cs, on, funding_points=funding)
    # same entries/exits; funding only subtracts from R for longs
    assert len(t_off) == len(t_on) >= 1
    for a, b in zip(t_off, t_on):
        assert b.funding_paid_r > 0.0
        assert b.r_multiple < a.r_multiple
        # funding term accounts for the full R difference (fees/slippage are 0).
        # 1e-3 absorbs the 4-dp rounding of r_multiple vs 6-dp funding_paid_r.
        assert abs((a.r_multiple - b.r_multiple) - b.funding_paid_r) < 1e-3


def test_trend_params_funding_enabled_defaults_true():
    assert TrendParams().funding_enabled is True
