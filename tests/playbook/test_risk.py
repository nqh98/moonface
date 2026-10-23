from moonface.core.models import Candle
from moonface.research.playbook.config import PlaybookParams
from moonface.research.playbook.setups import Setup, TRIGGERED
from moonface.research.playbook.risk import build_risk_plan, preferred_exit

H = 3_600_000


def _series(prices):
    return [Candle(i * H, p, p + 1.0, p - 1.0, p, 1.0) for i, p in enumerate(prices)]


def test_plan_initial_r_is_atr_normalised():
    s = Setup("trend_breakout", TRIGGERED, 110.0, 108.0, 109.0)
    plan = build_risk_plan(_series([100 + i * 0.1 for i in range(60)]), s,
                           PlaybookParams(), "atr_trail",
                           {"k_trail": 3.0, "max_bars": 96, "atr_period": 14})
    assert plan.entry == 110.0 and plan.stop == 108.0
    assert plan.exit_name == "atr_trail"
    assert plan.initial_r > 0


def test_preferred_exit_for_vol_expansion_is_fixed_bracket():
    name, p = preferred_exit("vol_compression_expansion", PlaybookParams())
    assert name == "fixed_bracket"
