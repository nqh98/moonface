# tests/test_practical_isolation.py
import inspect

import tools.practical.practical_search as cli
from moonface.core.exits import EXECUTABLE_EXITS, EXIT_REGISTRY
from moonface.research.practical import (exits_scaled, explore, families,
                                         pipeline, select, validate)


def test_lane_modules_do_not_reference_donchian_deploy_artifacts():
    forbidden = ("promotion/strategy.json", "journal/signals.jsonl",
                 "df7cc856", "donchian_trail")
    for mod in (exits_scaled, families, explore, select, validate, pipeline, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged():
    # the new exit must be runnable but NOT part of the academic research grid
    assert "mean_revert_reclaim" in EXECUTABLE_EXITS
    assert "mean_revert_reclaim" not in EXIT_REGISTRY
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}
