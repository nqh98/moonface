from __future__ import annotations

MIN_TRADES_PER_WEIGHT = 30


def allowed_p_eff(n_train_trades: int, m_per_weight: int) -> int:
    m = max(m_per_weight, MIN_TRADES_PER_WEIGHT)
    return n_train_trades // m


def check_power_budget(n_train_trades: int, p_eff: int, m_per_weight: int) -> bool:
    return 1 <= p_eff <= allowed_p_eff(n_train_trades, m_per_weight)
