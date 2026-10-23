# tests/test_playbook_isolation.py
import inspect

import tools.playbook.playbook_search as cli
from moonface.core.exits import EXECUTABLE_EXITS, EXIT_REGISTRY
from moonface.research.playbook import (backtest, config, engine, explore,
                                        families, journal, mtf, pipeline, quality,
                                        regime, risk, select, setups, validate)

LANE = (backtest, config, engine, explore, families, journal, mtf, pipeline,
        quality, regime, risk, select, setups, validate, cli)


def test_no_deploy_or_promotion_references():
    forbidden = ("promotion/strategy.json", "journal/signals.jsonl", "df7cc856")
    for mod in LANE:
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_lane_does_not_touch_donchian_or_other_closed_lanes():
    for mod in LANE:
        src = inspect.getsource(mod)
        assert "donchian_reval" not in src, f"{mod.__name__} touches donchian_reval"
        assert "research.system_search" not in src, (
            f"{mod.__name__} imports system_search")


def test_exit_registry_membership_unchanged():
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}


def test_lane_adds_no_new_executable_exit():
    used = {c.exit_name for c in families.all_playbook_configs()}
    assert used <= set(EXECUTABLE_EXITS)
    assert used == {"atr_trail", "chandelier", "donchian_trail"}
