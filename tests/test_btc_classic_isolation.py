# tests/test_btc_classic_isolation.py
import importlib
import inspect


def test_exit_registry_membership_unchanged():
    from moonface.core.exits import EXIT_REGISTRY
    # btc_classic must not register or remove any exit
    assert "atr_trail" in EXIT_REGISTRY
    before = set(EXIT_REGISTRY)
    importlib.import_module("moonface.research.btc_classic.grid")
    importlib.import_module("moonface.research.btc_classic.evaluate")
    from moonface.core.exits import EXIT_REGISTRY as after_reg
    assert set(after_reg) == before


def test_btc_classic_imports_no_dsr_machinery():
    import moonface.research.btc_classic.evaluate as ev
    import moonface.research.btc_classic.grid as gr
    import moonface.kernel.power_harness as ph
    for mod in (ev, gr, ph):
        src = inspect.getsource(mod)
        assert "dsr" not in src.lower()
        assert "deflat" not in src.lower()


def test_btc_classic_does_not_shadow_reused_builders():
    # Reuses edge/breadth code by import, never redefines it.
    import moonface.research.btc_classic.evaluate as ev
    from moonface.research.breadth.evaluate import score_records
    from moonface.research.edge.signals import donchian_break
    assert ev.score_records is score_records
    assert ev.price_signals.donchian_break is donchian_break
