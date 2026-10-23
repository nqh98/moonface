from __future__ import annotations

from moonface.research.breadth_internal.grid import (
    EXIT_NAME,
    EXIT_PARAMS,
    H,
    SignalSpec,
    _freeze_params,
)

# Derived (not tuned): h / bars_per_day = 48 / 6 = 8 trades of hold overlap.
BLOCK_LEN = 8


def hf_specs() -> list[SignalSpec]:
    return [
        SignalSpec(
            key="breadth_oscillator",
            builder="breadth_oscillator",
            params=_freeze_params({"window": 60, "z_in": 1.0, "base_period": 50}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
        SignalSpec(
            key="breadth_momentum",
            builder="breadth_momentum",
            params=_freeze_params({"n": 10, "thr": 0.10, "base_period": 50}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
        SignalSpec(
            key="breadth_accel",
            builder="breadth_accel",
            params=_freeze_params({"n": 5, "thr": 0.05, "base_period": 50}),
            exit_name=EXIT_NAME,
            exit_params=_freeze_params(EXIT_PARAMS),
            h=H,
        ),
    ]
