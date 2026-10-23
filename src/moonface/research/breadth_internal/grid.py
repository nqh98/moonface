from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

H = 48
EXIT_NAME = "atr_trail"
EXIT_PARAMS = {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}


def _freeze_params(params: dict[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType(dict(params))


@dataclass(frozen=True)
class SignalSpec:
    key: str
    builder: str
    params: MappingProxyType[str, Any]
    exit_name: str
    exit_params: MappingProxyType[str, Any]
    h: int


def all_specs() -> list[SignalSpec]:
    return [
        SignalSpec(
            key="breadth_thrust",
            builder="breadth_thrust",
            params=_freeze_params({
                "base_period": 50,
                "low_band": 0.40,
                "high_band": 0.60,
                "window": 6,
            }),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
        SignalSpec(
            key="net_new_highs",
            builder="net_new_highs",
            params=_freeze_params({"n": 20, "long_thr": 0.30, "short_thr": -0.30}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
        SignalSpec(
            key="breadth_divergence",
            builder="breadth_divergence",
            params=_freeze_params({"n": 20, "base_period": 50}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
        SignalSpec(
            key="dispersion_regime",
            builder="dispersion_regime",
            params=_freeze_params({"d": 10, "m_ma": 20, "window": 180, "p": 0.70}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
    ]
