# tests/test_pathsig_costs.py
from moonface.research.pathsig.costs import apply_costs


def test_costs_reduce_gross_r():
    net = apply_costs(gross_r=2.0, atr_frac=0.02, taker_bps=5.0,
                      slippage_bps=2.0, funding_r=0.1)
    # round-trip taker = 2*5bps = 0.001 of notional -> 0.001/0.02 = 0.05 R
    # slippage round-trip = 2*2bps = 0.0004 -> 0.02 R; funding 0.1 R
    assert net == round(2.0 - 0.05 - 0.02 - 0.1, 6)


def test_tighter_stop_costs_more_r():
    # smaller atr_frac (tighter ATR relative to price) => fees cost more in R
    wide = apply_costs(2.0, atr_frac=0.05, taker_bps=5.0, slippage_bps=0.0,
                       funding_r=0.0)
    tight = apply_costs(2.0, atr_frac=0.01, taker_bps=5.0, slippage_bps=0.0,
                        funding_r=0.0)
    assert tight < wide
