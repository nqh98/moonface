from moonface.core.bundle import DataBundle
from moonface.kernel.synth import make_candles
from moonface.models import evaluate as evaluate_module
from moonface.models.evaluate import Signal
from moonface.strategies.registry import get_strategy_module, supports_strategy
from tests.test_signal_evaluate import STRATEGY


def test_registry_resolves_donchian():
    module = get_strategy_module("donchian_break")
    assert module is not None
    assert module.family == "donchian_break"


def test_registry_rejects_unknown_family():
    assert get_strategy_module("astrology") is None
    assert supports_strategy("astrology") is False


def test_public_evaluate_delegates_to_registered_module(monkeypatch):
    expected = Signal("WAIT", None, None, None, "delegated")

    class FakeModule:
        family = "donchian_break"

        def validate(self, strategy):
            return True

        def evaluate(self, strategy, bundle):
            return expected

    monkeypatch.setattr(
        evaluate_module, "get_strategy_module", lambda family: FakeModule()
    )
    bundle = DataBundle(candles=make_candles(3))
    assert evaluate_module.evaluate(STRATEGY, bundle) == expected


def test_public_evaluate_fails_closed_for_unregistered_family(monkeypatch):
    monkeypatch.setattr(
        evaluate_module, "get_strategy_module", lambda family: None
    )
    bundle = DataBundle(candles=make_candles(3))
    signal = evaluate_module.evaluate(STRATEGY, bundle)
    assert signal.decision == "WAIT"
    assert signal.reason == "unsupported strategy family: donchian_break"
