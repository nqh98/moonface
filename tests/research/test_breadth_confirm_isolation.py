import importlib
import inspect

import moonface.research.breadth_confirm.evaluate as bc_eval
import moonface.research.breadth_confirm.grid as bc_grid
import moonface.research.breadth_confirm.universe_slice as bc_uni
from moonface.research.breadth_confirm.grid import net_new_highs_spec
from moonface.research.breadth_internal.grid import all_specs


def test_frozen_spec_is_byte_identical_to_breadth_internal():
    confirm_spec = net_new_highs_spec()
    source = next(s for s in all_specs() if s.key == "net_new_highs")
    assert confirm_spec.key == source.key
    assert confirm_spec.builder == source.builder
    assert dict(confirm_spec.params) == dict(source.params)
    assert confirm_spec.exit_name == source.exit_name
    assert dict(confirm_spec.exit_params) == dict(source.exit_params)
    assert confirm_spec.h == source.h


def test_breadth_confirm_imports_no_deflation_machinery():
    for mod in (bc_eval, bc_grid, bc_uni):
        src = inspect.getsource(mod)
        assert "dsr" not in src.lower()
        assert "deflat" not in src.lower()


def test_breadth_confirm_does_not_mutate_breadth_packages():
    # No breadth_confirm module rebinds attributes on the frozen lanes.
    for name in (
        "moonface.research.breadth_confirm.evaluate",
        "moonface.research.breadth_confirm.grid",
        "moonface.research.breadth_confirm.universe_slice",
    ):
        src = inspect.getsource(importlib.import_module(name))
        assert "breadth.signals." not in src.replace("import", "")  # no attribute rebind
        assert ".params =" not in src
        assert ".EXIT_REGISTRY" not in src


def test_exit_registry_membership_unchanged():
    from moonface.core.exits import EXIT_REGISTRY
    assert "atr_trail" in EXIT_REGISTRY
