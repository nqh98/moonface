from moonface.research.playbook.config import PlaybookParams, SUPPORTIVE, UPTREND
from moonface.research.playbook.families import all_playbook_configs, GRID_SIZE


def test_default_params_are_theory_frozen():
    p = PlaybookParams()
    assert (p.ma_fast, p.ma_mid, p.ma_slow) == (20, 50, 200)
    assert p.atr_period == 14
    assert UPTREND in SUPPORTIVE


def test_grid_is_small_and_declared():
    cfgs = all_playbook_configs()
    assert len(cfgs) == GRID_SIZE == 12
    # labels unique
    assert len({c.label for c in cfgs}) == len(cfgs)
    # every exit already resolvable in EXECUTABLE_EXITS (no new exit added)
    from moonface.core.exits import EXECUTABLE_EXITS
    assert all(c.exit_name in EXECUTABLE_EXITS for c in cfgs)
    # grid sweeps only the two declared axes around frozen defaults
    assert {c.slope_n for c in cfgs} == {10, 20}
    assert {c.donchian_n for c in cfgs} == {20, 55}
    assert {c.exit_name for c in cfgs} == {"atr_trail", "chandelier", "donchian_trail"}
