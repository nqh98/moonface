from moonface.core.models import Candle, ActionPlan
from moonface.features.simulate import simulate_trade
from moonface.kernel.audit import (
    cost_sweep, CostRow,
    fixed_tp_plans_from_breakouts, reconcile_vs_engine, _independent_r,
)
from moonface.research.trend_sim import TrendParams


def _candle(ts, o, h, lo, c):
    return Candle(ts, o, h, lo, c, 1.0)


def test_fixed_tp_plans_build_valid_buy_brackets_at_breakouts():
    # flat then one step up: exactly one breakout (at the step bar)
    closes = [10, 10, 10, 10, 13, 13, 13, 13]
    cs = [Candle(i, c, c, c, c, 1.0) for i, c in enumerate(closes)]
    plans = fixed_tp_plans_from_breakouts(cs, n=2, rr1=1.0, rr2=2.0)
    assert len(plans) == 1
    idx, plan = plans[0]
    assert idx == 4 and plan.side == "BUY"
    assert plan.stop_loss < plan.entry < plan.take_profit_1 <= plan.take_profit_2


def test_reconcile_vs_engine_matches_within_tolerance_on_synthetic():
    # uptrend, gain 3.0 > spread 1.0 so breakouts fire; ranges exercise fills
    cs = []
    for i in range(40):
        p = 100.0 + i * 3.0
        cs.append(Candle(i, p, p + 1.0, p - 1.0, p, 1.0))
    rec = reconcile_vs_engine(cs, n=5, fee_rate=0.00045, slippage=0.0005)
    assert rec.n_trades >= 1
    # The independent re-derivation must match the engine to the cent.
    assert rec.max_abs_r_diff < 1e-6


def test_independent_r_matches_engine_stop_first_on_ambiguous_bar():
    # one BUY bracket; a future bar whose range spans BOTH stop and tp1 must
    # resolve stop-first (conservative) in both the engine and the re-derivation.
    plan = ActionPlan(side="BUY", bias="LONG", entry=100.0, stop_loss=95.0,
                      take_profit_1=105.0, take_profit_2=110.0,
                      risk_percentage=0.0, source_timeframe="audit")
    candles = [Candle(0, 100, 100, 100, 100, 1.0),   # entry bar (idx 0)
               Candle(1, 100, 106, 94, 100, 1.0)]    # low 94 <= stop, high 106 >= tp1
    eng = simulate_trade(plan, candles[1:], fee_rate=0.001, slippage=0.0,
                         entry_index=0)
    indep = _independent_r(plan, candles[1:], fee_rate=0.001, slippage=0.0)
    assert eng is not None and eng.r_multiple is not None and indep is not None
    assert eng.outcome == "SL"
    assert abs(eng.r_multiple - indep) < 1e-6


def test_cost_sweep_expectancy_is_monotone_nonincreasing_in_cost():
    # uptrend (gain 3.0 > spread 1.0) so trades exist; cost never changes trade
    # selection here, so higher total cost strictly lowers expectancy.
    cs = []
    for i in range(60):
        p = 100.0 + i * 3.0
        cs.append(_candle(i, p, p + 1.0, p - 1.0, p))
    params = TrendParams(entry_n=5, trail_n=3, atr_period=14, k_stop=2.0,
                         long_only=True, fee_rate=0.0, slippage=0.0, funding_enabled=False)
    rows = cost_sweep(cs, None, params,
                      fee_grid=[0.0, 0.00045, 0.001],
                      slip_grid=[0.0, 0.0005])
    assert len(rows) == 3 * 2
    assert all(isinstance(r, CostRow) for r in rows)
    # cheapest combo is first and has the highest expectancy
    assert rows[0].fee == 0.0 and rows[0].slippage == 0.0
    # the nested grid is NOT cost-ordered, so sort by total cost before checking
    ordered = sorted(rows, key=lambda r: r.fee + r.slippage)
    for prev, cur in zip(ordered, ordered[1:]):
        assert cur.expectancy_r <= prev.expectancy_r + 1e-9
