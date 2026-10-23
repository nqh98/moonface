import importlib
import inspect

import moonface.research.breadth_confirm.momentum_grid as mg
from moonface.research.breadth_confirm.momentum_grid import breadth_momentum_spec
from moonface.research.breadth_internal.hf_grid import hf_specs


def test_frozen_spec_is_byte_identical_to_hf_grid():
    confirm_spec = breadth_momentum_spec()
    source = next(s for s in hf_specs() if s.key == "breadth_momentum")
    assert confirm_spec.key == source.key
    assert confirm_spec.builder == source.builder
    assert dict(confirm_spec.params) == dict(source.params)
    assert confirm_spec.exit_name == source.exit_name
    assert dict(confirm_spec.exit_params) == dict(source.exit_params)
    assert confirm_spec.h == source.h


def test_momentum_grid_imports_no_deflation_machinery():
    src = inspect.getsource(mg)
    assert "dsr" not in src.lower()
    assert "deflat" not in src.lower()


def test_momentum_grid_does_not_mutate_breadth_packages():
    src = inspect.getsource(importlib.import_module(
        "moonface.research.breadth_confirm.momentum_grid"))
    assert ".params =" not in src
    assert ".EXIT_REGISTRY" not in src


def test_exit_registry_membership_unchanged():
    from moonface.core.exits import EXIT_REGISTRY
    assert "atr_trail" in EXIT_REGISTRY
