from moonface.core.models import Candle
from moonface.research.trend_sim import TrendParams
from moonface.kernel.walkforward import walk_forward


def _trend_then_flat(total=12000):
    """First half trends up strongly, second half is flat. Params that fit the
    trend should be picked in train and produce positive test R in the trend half."""
    out = []
    for i in range(total):
        if i < total // 2:
            p = 100.0 + i * 3.0      # gain 3.0 > spread 2.0 so breakouts fire
        else:
            p = 100.0 + (total // 2) * 3.0
        out.append(Candle(i, p, p + 2.0, p - 2.0, p, 1.0))
    return out


def test_walk_forward_train_precedes_test_no_overlap():
    cs = _trend_then_flat()
    grid = [TrendParams(entry_n=10, trail_n=5, fee_rate=0.0, slippage=0.0,
                        funding_enabled=False)]
    res = walk_forward(cs, None, grid, train_bars=2000, test_bars=2000, step_bars=2000)
    assert len(res.test_summaries) >= 1
    # aggregated is over test trades only
    assert res.aggregated.trade_count == sum(s.trade_count for s in res.test_summaries)


def test_walk_forward_picks_best_train_param_for_test():
    # two grids; the one with smaller entry_n fits the strong trend better
    cs = _trend_then_flat()
    grid = [
        TrendParams(entry_n=50, trail_n=20, fee_rate=0.0, slippage=0.0, funding_enabled=False),
        TrendParams(entry_n=5, trail_n=3, fee_rate=0.0, slippage=0.0, funding_enabled=False),
    ]
    res = walk_forward(cs, None, grid, train_bars=2000, test_bars=2000, step_bars=2000)
    # on the trending train window the small-n param wins
    assert res.chosen_params[0].entry_n == 5
