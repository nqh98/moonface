from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.power import allowed_p_eff
from moonface.models.engine.moe.regimes import TRADEABLE, MoeRegime


@dataclass(frozen=True)
class EdgeSample:
    regime: MoeRegime
    expert: str
    direction: int
    net_r: float


def _james_stein_lambda(n_r: int, k: int, snr: float) -> float:
    denom = k + max(n_r - k - 2, 0) * snr
    lam = k / denom if denom > 0 else 1.0
    return max(0.0, min(lam, 1.0))


def fit_weights(
    samples: list[EdgeSample],
    experts: list[str],
    cfg: MoeConfig,
    n_train_trades: int,
) -> dict[MoeRegime, dict[str, float]]:
    rs: dict[tuple[MoeRegime, str], list[float]] = {}
    for sample in samples:
        rs.setdefault((sample.regime, sample.expert), []).append(sample.net_r)

    W: dict[MoeRegime, dict[str, float]] = {regime: {expert: 0.0 for expert in experts} for regime in TRADEABLE}
    k = len(experts)
    for regime in TRADEABLE:
        raw_edges = {}
        for expert in experts:
            vals = rs.get((regime, expert), [])
            raw_edges[expert] = (fmean(vals), len(vals)) if vals else (0.0, 0)
        pos = {expert: (max(0.0, mean), n) for expert, (mean, n) in raw_edges.items()}
        active = {expert: value for expert, (value, _count) in pos.items() if value > 0.0}
        if active:
            prior = fmean(active.values())
            for expert in experts:
                value, count = pos[expert]
                if value <= 0.0:
                    W[regime][expert] = 0.0
                    continue
                lam = _james_stein_lambda(count, k, cfg.shrink_snr)
                W[regime][expert] = (1.0 - lam) * value + lam * prior
        mx = max(W[regime].values()) if W[regime] else 0.0
        if mx > 0.0:
            for expert in experts:
                if W[regime][expert] < cfg.l1_frac * mx:
                    W[regime][expert] = 0.0

    allowed = allowed_p_eff(n_train_trades, cfg.m_per_weight)
    cells = [(regime, expert, W[regime][expert]) for regime in TRADEABLE for expert in experts if W[regime][expert] > 0.0]
    cells.sort(key=lambda cell: cell[2], reverse=True)
    for regime, expert, _value in cells[allowed:]:
        W[regime][expert] = 0.0
    return W


def p_eff(W: dict[MoeRegime, dict[str, float]]) -> int:
    return sum(1 for row in W.values() for value in row.values() if value > 0.0)
