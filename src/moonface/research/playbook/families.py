"""Frozen default playbook + the small declared exploratory grid (theory-frozen
defaults perturbed on two axes x three exits = 12 configs). DSR n_trials = 12.
The lane names only exits already in EXECUTABLE_EXITS; it adds none."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.research.playbook.config import PlaybookParams

_AP = 14

# (exit_name, exit_params) — all resolve in EXECUTABLE_EXITS already
_EXITS: list[tuple[str, dict]] = [
    ("atr_trail", {"k_trail": 3.0, "max_bars": 96, "atr_period": _AP}),
    ("chandelier", {"atr_mult": 3.0, "max_bars": 96, "atr_period": _AP}),
    ("donchian_trail", {"k_stop": 2.0, "trail_n": 20, "max_bars": 96,
                        "atr_period": _AP}),
]

_SLOPE_N = (10, 20)
_DONCHIAN_N = (20, 55)
GRID_SIZE = len(_EXITS) * len(_SLOPE_N) * len(_DONCHIAN_N)  # 12


@dataclass(frozen=True)
class PlaybookConfig:
    label: str
    params: PlaybookParams
    exit_name: str
    exit_params: dict
    slope_n: int
    donchian_n: int


def all_playbook_configs() -> list[PlaybookConfig]:
    out: list[PlaybookConfig] = []
    for slope_n in _SLOPE_N:
        for donchian_n in _DONCHIAN_N:
            params = PlaybookParams(slope_n=slope_n, donchian_n=donchian_n)
            for exit_name, ep in _EXITS:
                label = f"slope{slope_n}:don{donchian_n}:{exit_name}"
                out.append(PlaybookConfig(label=label, params=params,
                                          exit_name=exit_name, exit_params=dict(ep),
                                          slope_n=slope_n, donchian_n=donchian_n))
    return out
