from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.signal_types import Signal, sentinel_extended, wait
from moonface.strategies.spec import PromotedStrategy
from moonface.strategies.registry import get_strategy_module


def evaluate(strategy: PromotedStrategy, bundle: DataBundle) -> Signal:
    """Signal for the last closed candle, delegated to the registered strategy
    module for this family."""
    module = get_strategy_module(strategy.family)
    if module is None:
        return wait(f"unsupported strategy family: {strategy.family}")
    return module.evaluate(strategy, bundle)


# public names (preferred); underscore aliases kept for back-compat
_wait = wait
_sentinel_extended = sentinel_extended
