from __future__ import annotations

from dataclasses import dataclass

from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.regimes import TRADEABLE, MoeRegime


def master_score(s_by_expert: dict[str, float], W_row: dict[str, float], eps: float) -> float:
    num = sum(W_row.get(expert, 0.0) * score for expert, score in s_by_expert.items())
    den = sum(W_row.values()) + eps
    return num / den


def confluence(s_by_expert: dict[str, float], W_row: dict[str, float], side: int) -> int:
    return sum(
        1
        for expert, weight in W_row.items()
        if weight > 0.0
        and (1 if s_by_expert.get(expert, 0.0) > 0 else -1 if s_by_expert.get(expert, 0.0) < 0 else 0) == side
    )


@dataclass(frozen=True)
class MoeDecision:
    action: str
    direction: int
    regime: MoeRegime
    score: float
    detail: str


def decide_moe(
    s_by_expert: dict[str, float],
    regime: MoeRegime,
    W: dict[MoeRegime, dict[str, float]],
    cfg: MoeConfig,
) -> MoeDecision:
    if regime not in TRADEABLE:
        return MoeDecision("WAIT", 0, regime, 0.0, f"{regime.value} not tradeable")
    row = W.get(regime, {})
    m = master_score(s_by_expert, row, cfg.eps)
    side = 1 if m > 0 else -1 if m < 0 else 0
    if side == 0 or abs(m) < cfg.tau:
        return MoeDecision("WAIT", 0, regime, m, f"|M|={abs(m):.3f} < tau={cfg.tau}")
    if confluence(s_by_expert, row, side) < cfg.q_confluence:
        return MoeDecision("WAIT", 0, regime, m, "confluence below q")
    return MoeDecision("ENTER", side, regime, m, f"ENTER dir={side} M={m:.3f}")
