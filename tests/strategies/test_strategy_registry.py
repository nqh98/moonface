from moonface.strategies.registry import (
    _REGISTERED, get_strategy_module, register, supports_strategy,
)


def test_builtin_donchian_is_discovered():
    assert supports_strategy("donchian_break")
    mod = get_strategy_module("donchian_break")
    assert mod is not None and mod.family == "donchian_break"


def test_unknown_family_is_none():
    assert get_strategy_module("does_not_exist") is None
    assert not supports_strategy("does_not_exist")


def test_register_decorator_returns_class():
    try:
        @register
        class Dummy:
            family = "dummy_test_family"

            def validate(self, s):
                return True

            def evaluate(self, s, b):
                return None

        # @register returns the class unchanged and records it for fallback
        # discovery; pop it afterwards so it never leaks into other tests.
        assert Dummy.family == "dummy_test_family"
        assert _REGISTERED["dummy_test_family"] is Dummy
    finally:
        _REGISTERED.pop("dummy_test_family", None)
