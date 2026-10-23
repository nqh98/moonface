"""Gross-R -> net-R cost model: round-trip taker fee + slippage + funding.

Fees and slippage are fractions of notional; since 1 R of price move equals
atr_frac of notional, a notional cost c becomes c / atr_frac in R. funding_r is
supplied already in R (signed accrual over the hold)."""
from __future__ import annotations


def apply_costs(gross_r: float, atr_frac: float, taker_bps: float,
                slippage_bps: float, funding_r: float) -> float:
    if atr_frac <= 0:
        return gross_r - funding_r
    taker_frac = 2.0 * taker_bps / 1e4        # entry + exit
    slip_frac = 2.0 * slippage_bps / 1e4
    cost_r = (taker_frac + slip_frac) / atr_frac
    return round(gross_r - cost_r - funding_r, 6)
