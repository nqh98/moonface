# tests/test_btcspec_isolation.py
import inspect

import tools.btcspec.btcspec_search as cli
import tools.btcspec.btcspec_s2_search as cli_s2
import tools.btcspec.btcspec_s3_search as cli_s3
from moonface.core.exits import (BTCSPEC_EXIT_REGISTRY, EXECUTABLE_EXITS,
                                        EXIT_REGISTRY)
from moonface.research.btcspec import (exits_scaled, explore, families, families_s2,
                                       families_s3, pipeline, select, validate)


def test_lane_modules_do_not_reference_deploy_promotion_artifacts():
    forbidden = ("promotion/strategy.json", "journal/signals.jsonl", "df7cc856")
    for mod in (exits_scaled, families, families_s2, families_s3, explore, select,
                validate, pipeline, cli, cli_s2, cli_s3):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged():
    assert "chandelier" in BTCSPEC_EXIT_REGISTRY
    assert "chandelier" in EXECUTABLE_EXITS
    assert "chandelier" not in EXIT_REGISTRY
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}


def test_lane_does_not_touch_closed_lane_packages():
    for mod in (exits_scaled, families, families_s2, families_s3, explore, select,
                validate, pipeline, cli, cli_s2, cli_s3):
        src = inspect.getsource(mod)
        assert "research.practical" not in src, f"{mod.__name__} imports practical lane"
        assert "research.system_search" not in src, f"{mod.__name__} imports system_search"


def test_slice2_grid_has_no_new_executable_exit():
    # vol_expansion reuses fixed_bracket (already in EXIT_REGISTRY); the lane adds none.
    from moonface.research.btcspec.families_s2 import all_explore_configs_s2
    exit_names = {c.exit_name for c in all_explore_configs_s2()}
    assert exit_names == {"atr_trail", "donchian_trail", "chandelier", "fixed_bracket"}
    assert "fixed_bracket" in EXIT_REGISTRY  # not a new exit


def test_slice3_grid_has_no_new_executable_exit():
    # the fade families reuse fixed_bracket (already in EXIT_REGISTRY); the lane adds none.
    from moonface.research.btcspec.families_s3 import all_explore_configs_s3
    exit_names = {c.exit_name for c in all_explore_configs_s3()}
    assert exit_names == {"atr_trail", "donchian_trail", "chandelier", "fixed_bracket"}
    assert "fixed_bracket" in EXIT_REGISTRY  # not a new exit
