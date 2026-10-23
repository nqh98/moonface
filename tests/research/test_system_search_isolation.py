import inspect

import tools.lanes.system_search as cli
from moonface.research import system_search, system_cells, system_battery


def test_lane_modules_do_not_reference_donchian_deploy_artifacts():
    """Static guard: the system-search lane must not touch the frozen Donchian
    Slice-3 deployment surfaces."""
    forbidden = ("promotion/strategy.json", "journal/signals.jsonl",
                 "df7cc856", "donchian_trail")
    for mod in (system_search, system_cells, system_battery, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_research_cells_use_only_research_exits():
    from moonface.core.exits import EXIT_REGISTRY
    for cell in system_cells.all_system_cells():
        assert cell.exit_name in EXIT_REGISTRY
