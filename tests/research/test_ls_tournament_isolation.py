import inspect

import tools.ls_tournament.ls_tournament as cli
from moonface.core.exits import EXECUTABLE_EXITS, EXIT_REGISTRY
from moonface.research.ls_tournament import evaluate, explore, grid, pipeline, select, validate


def test_lane_modules_do_not_reference_deploy_artifacts():
    forbidden = ("promotion/strategy.json", "promotion/engine.json",
                 "journal/signals.jsonl", "df7cc856")
    for mod in (grid, evaluate, explore, select, validate, pipeline, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged():
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}
    for ex in {c.exit_name for c in grid.all_configs(["2h"])}:
        assert ex in EXECUTABLE_EXITS
