"""Funding-cost primitives for held perp positions.

Funding is charged every 8h on USDT-M perps. A LONG pays positive funding
(crowded long); a SHORT receives it. Cost is kept as a separate, auditable
term from fees: r_multiple = (pnl - fees - funding_cost) / risk.
"""
from __future__ import annotations

from moonface.core.models import Side


def held_funding_rates(
    points: list[tuple[int, float]], entry_ms: int, exit_ms: int
) -> list[tuple[int, float]]:
    """Funding prints whose timestamp falls strictly inside (entry_ms, exit_ms].

    A print at exactly entry_ms is excluded — the position was not yet open when
    that payment was settled. A print at exactly exit_ms is included.
    """
    return [(t, r) for t, r in points if entry_ms < t <= exit_ms]


def funding_cost_pct(rates: list[float], side: Side) -> float:
    """Net funding as a fraction of notional, signed so that a positive value is a
    cost (reduces PnL). Longs pay +rate; shorts receive +rate (i.e. pay -rate)."""
    net = sum(rates)
    return net if side == "BUY" else -net


def funding_cost_r(
    points_in_hold: list[tuple[int, float]], side: Side, risk: float, notional: float
) -> float:
    """Funding cost expressed in R-multiple units.

    funding_paid = funding_cost_pct * notional ; cost_r = funding_paid / risk.
    `points_in_hold` is the already-windowed list (see `held_funding_rates`).
    """
    if risk <= 0:
        return 0.0
    rates = [r for _, r in points_in_hold]
    return round(funding_cost_pct(rates, side) * notional / risk, 6)
