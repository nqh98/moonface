from __future__ import annotations

from moonface.models.engine.v3.config_v3 import EngineConfigV3


def q_floor_for(name: str, cfg: EngineConfigV3) -> float:
    floors = {
        "BREAKOUT": cfg.q_floor_breakout,
        "PULLBACK": cfg.q_floor_pullback,
        "REVERSION": cfg.q_floor_reversion,
    }
    return floors[name]


def size_from_quality(name: str, quality: float, cfg: EngineConfigV3) -> float:
    """f(q) = clip((q - q_floor)/(1 - q_floor), 0, 1); fraction = base * f,
    capped at max_fraction. Below the floor -> 0.0 (the sole veto)."""
    floor = q_floor_for(name, cfg)
    if quality < floor or floor >= 1.0:
        return 0.0
    f = (quality - floor) / (1.0 - floor)
    f = 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)
    return min(
        cfg.base_fraction + f * (cfg.max_fraction - cfg.base_fraction),
        cfg.max_fraction,
    )
