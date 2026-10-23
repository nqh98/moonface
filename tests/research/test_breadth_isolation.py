import inspect

import tools.breadth.breadth as cli
from moonface.core.exits import EXECUTABLE_EXITS, EXIT_REGISTRY
from moonface.research.breadth import evaluate, gates, grid, signals


def test_lane_does_not_reference_deploy_artifacts() -> None:
    forbidden = (
        "promotion/strategy.json",
        "promotion/engine.json",
        "journal/signals.jsonl",
        "df7cc856",
    )
    for mod in (signals, grid, evaluate, gates, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged() -> None:
    assert set(EXIT_REGISTRY) == {
        "horizon_hold",
        "atr_trail",
        "horizon_wide_stop",
        "breakeven_horizon",
        "fixed_bracket",
    }
    assert grid.EXIT_NAME in EXECUTABLE_EXITS


def test_lane_only_reads_atr_trail() -> None:
    assert {cell.exit_name for cell in grid.all_cells()} == {"atr_trail"}
