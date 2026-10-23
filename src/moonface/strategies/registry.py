from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import entry_points
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from moonface.core.bundle import DataBundle
    from moonface.models.evaluate import Signal
    from moonface.strategies.spec import PromotedStrategy

_GROUP = "moonface.strategies"
_FALLBACK_PKG = "moonface.strategies.impls"

# Classes that tagged themselves via @register, used only by the
# source-checkout fallback when entry-point metadata is unavailable.
_REGISTERED: dict[str, type] = {}


class StrategyModule(Protocol):
    family: str

    def validate(self, strategy: "PromotedStrategy") -> bool: ...

    def evaluate(self, strategy: "PromotedStrategy",
                 bundle: "DataBundle") -> "Signal": ...


def register(cls):
    """Decorator: tag a strategy class for source-checkout fallback discovery."""
    _REGISTERED[cls.family] = cls
    return cls


def _from_entry_points() -> dict[str, StrategyModule]:
    out: dict[str, StrategyModule] = {}
    for ep in entry_points(group=_GROUP):
        cls = ep.load()
        inst = cls()
        out[inst.family] = inst
    return out


def _from_fallback() -> dict[str, StrategyModule]:
    pkg = importlib.import_module(_FALLBACK_PKG)
    for info in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{_FALLBACK_PKG}.{info.name}")
    return {fam: cls() for fam, cls in _REGISTERED.items()}


_CACHE: dict[str, StrategyModule] | None = None


def _registry() -> dict[str, StrategyModule]:
    global _CACHE
    if _CACHE is None:
        mods = {**_from_fallback(), **_from_entry_points()}
        _CACHE = mods
    return _CACHE


def get_strategy_module(family: str) -> StrategyModule | None:
    return _registry().get(family)


def supports_strategy(family: str) -> bool:
    return family in _registry()
