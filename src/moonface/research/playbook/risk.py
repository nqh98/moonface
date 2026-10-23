from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.playbook.config import PlaybookParams
from moonface.research.playbook.setups import Setup

_AP = 14
# advisory per-setup exits surfaced in the live journal (NOT used for backtest R)
_PREFERRED = {
    "trend_breakout": ("donchian_trail", {"k_stop": 2.0, "trail_n": 20,
                                          "max_bars": 96, "atr_period": _AP}),
    "continuation_breakout": ("donchian_trail", {"k_stop": 2.0, "trail_n": 20,
                                                 "max_bars": 96, "atr_period": _AP}),
    "pullback_reclaim": ("chandelier", {"atr_mult": 3.0, "max_bars": 96,
                                        "atr_period": _AP}),
    "vol_compression_expansion": ("fixed_bracket", {"k_stop": 1.0, "m_tp": 4.0,
                                                    "atr_period": _AP}),
    "higher_low_reclaim": ("atr_trail", {"k_trail": 3.0, "max_bars": 96,
                                         "atr_period": _AP}),
    "failed_breakdown_reclaim": ("atr_trail", {"k_trail": 2.0, "max_bars": 96,
                                               "atr_period": _AP}),
}


@dataclass(frozen=True)
class RiskPlan:
    entry: float
    invalidation: float
    stop: float
    initial_r: float
    exit_name: str
    exit_params: dict
    early_exit_level: float


def preferred_exit(setup_name: str, params: PlaybookParams) -> tuple[str, dict]:
    name, p = _PREFERRED.get(setup_name, _PREFERRED["trend_breakout"])
    return name, dict(p)


def build_risk_plan(h1_prefix: list[Candle], setup: Setup, params: PlaybookParams,
                    exit_name: str, exit_params: dict) -> RiskPlan:
    a = atr(h1_prefix, params.atr_period)
    stop = setup.invalidation
    risk_price = max(setup.entry - stop, 0.0)
    initial_r = risk_price / a if a > 0 else 0.0
    return RiskPlan(entry=setup.entry, invalidation=setup.invalidation, stop=stop,
                    initial_r=round(initial_r, 4), exit_name=exit_name,
                    exit_params=dict(exit_params), early_exit_level=setup.ref_level)
