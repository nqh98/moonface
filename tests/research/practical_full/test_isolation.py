"""The practical-full lane must stay PAPER-only: never reference deploy/Donchian
promotion artifacts, and never widen the academic EXIT_REGISTRY."""
import inspect

import tools.practical_full.btc_practical_full as cli
from moonface.core.exits import EXECUTABLE_EXITS, EXIT_REGISTRY
from moonface.research.practical_full import grid, select_full, validate_full


def test_lane_modules_do_not_reference_deploy_artifacts():
    forbidden = ("promotion/strategy.json", "promotion/engine.json",
                 "journal/signals.jsonl", "df7cc856", "donchian_trail")
    for mod in (grid, select_full, validate_full, cli):
        src = inspect.getsource(mod)
        for needle in forbidden:
            assert needle not in src, f"{mod.__name__} references {needle}"


def test_exit_registry_membership_unchanged():
    # the lane resolves exits via EXECUTABLE_EXITS but never enlarges the
    # academic research grid (which would recalibrate concluded-domain DSR).
    assert set(EXIT_REGISTRY) == {"horizon_hold", "atr_trail", "horizon_wide_stop",
                                  "breakeven_horizon", "fixed_bracket"}
    for ex in {c.exit_name for c in grid.all_configs(["2h", "4h"])}:
        assert ex in EXECUTABLE_EXITS
