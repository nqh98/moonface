from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

EXIT_NAME = "atr_trail"
EXIT_PARAMS = {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}


def _freeze(params: dict[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType(dict(params))


@dataclass(frozen=True)
class SignalSpec:
    key: str
    kind: str  # "price" | "funding"
    builder: str  # function name in research.edge.signals, or "funding_fade"
    params: MappingProxyType[str, Any]
    exit_name: str
    exit_params: MappingProxyType[str, Any]


def _spec(key: str, kind: str, builder: str, params: dict[str, Any]) -> SignalSpec:
    return SignalSpec(
        key=key,
        kind=kind,
        builder=builder,
        params=_freeze(params),
        exit_name=EXIT_NAME,
        exit_params=_freeze(EXIT_PARAMS),
    )


def all_specs() -> list[SignalSpec]:
    return [
        _spec("trend", "price", "ma_cross", {"fast": 20, "slow": 100}),
        _spec("breakout", "price", "donchian_break", {"n": 55}),
        _spec("momentum", "price", "roc_sign", {"period": 24}),
        _spec("channel", "price", "atr_channel_break", {"k": 1.5, "atr_period": 14}),
        _spec("meanrev", "price", "reversion_in_range",
              {"period": 14, "low": 30, "high": 70}),
        _spec("funding_fade", "funding", "funding_fade", {"window": 180, "z_thr": 2.0}),
    ]
