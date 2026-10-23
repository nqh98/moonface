import inspect

import moonface.research.breadth_confirm.xasset_grid as xg
from moonface.research.breadth_confirm.xasset_grid import lead_specs
from moonface.research.breadth_internal.grid import all_specs
from moonface.research.breadth_internal.hf_grid import hf_specs


def test_leads_are_byte_identical_to_home_grids():
    specs = {s.key: s for s in lead_specs()}
    nnh_src = next(s for s in all_specs() if s.key == "net_new_highs")
    mom_src = next(s for s in hf_specs() if s.key == "breadth_momentum")
    for confirm, source in ((specs["net_new_highs"], nnh_src),
                            (specs["breadth_momentum"], mom_src)):
        assert confirm.builder == source.builder
        assert dict(confirm.params) == dict(source.params)
        assert confirm.exit_name == source.exit_name
        assert dict(confirm.exit_params) == dict(source.exit_params)
        assert confirm.h == source.h


def test_xasset_grid_imports_no_deflation_machinery():
    src = inspect.getsource(xg)
    assert "dsr" not in src.lower()
    assert "deflat" not in src.lower()


def test_exit_registry_membership_unchanged():
    from moonface.core.exits import EXIT_REGISTRY
    assert "atr_trail" in EXIT_REGISTRY
