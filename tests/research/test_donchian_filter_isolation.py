import inspect
from dataclasses import replace

import tools.donchian_filter.donchian_filter as cli
from moonface.core.exits import EXIT_REGISTRY
from moonface.research.donchian_filter import adx, data, evaluate, grid, select
from tools.engine.swing_donchian import _BASE


def test_lane_never_touches_deploy_artifacts():
    forbidden = ("promotion/", "journal/", "promotion.json", "signals.jsonl")
    for mod in (adx, data, evaluate, grid, select, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged():
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}


def test_base_config_byte_frozen():
    assert _BASE.entry_n == 20 and _BASE.trail_n == 10 and _BASE.atr_period == 14
    assert _BASE.k_stop == 2.0 and _BASE.long_only is True
    assert grid.deployed_base() == replace(_BASE, entry_n=40, trail_n=20)
