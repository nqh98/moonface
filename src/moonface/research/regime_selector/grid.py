from __future__ import annotations

from dataclasses import dataclass

# --- frozen non-Donchian bases (mid axis points of the practical grid) ---
TREND_FAMILY = "atr_channel_break"
TREND_PARAMS = {"atr_period": 14, "k": 1.5}
TREND_EXIT = "atr_trail"
TREND_EXIT_PARAMS = {"k_trail": 2.0, "max_bars": 120, "atr_period": 14}
TREND_H = 48

MR_FAMILY = "reversion_in_range"
MR_PARAMS = {"period": 14, "low": 25, "high": 75}
MR_EXIT = "fixed_bracket"
MR_EXIT_PARAMS = {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
MR_H = 24

# --- macro regimes (ids into regime_overlay.regime.REGIME_DEFS) ---
REGIME_IDS = ("R1", "R3")            # equity_riskon (primary), riskon_calm
RISKOFF_ACTIONS = ("switch", "wait")  # switch-to-MR | go-flat
CONTROL_KINDS = ("always_trend", "always_mr", "swap")


@dataclass(frozen=True)
class Cell:
    cell_id: str
    regime_id: str
    riskoff_action: str


CELLS = tuple(
    Cell(cell_id=f"{rid}-{act}", regime_id=rid, riskoff_action=act)
    for rid in REGIME_IDS
    for act in RISKOFF_ACTIONS
)
N_TRIALS = len(CELLS)

# --- windows (reuse the regime-overlay split exactly) ---
TRAIN_START = 1577836800000       # 2020-01-01
TRAIN_END = 1698796800000         # 2023-11-01
VALIDATE_START = TRAIN_END
VALIDATE_END = 1740787200000      # 2025-03-01
SEALED_START = VALIDATE_END
SEALED_END = 1782300000000        # ~2026-06-24

BTC_SYMBOL = "BTCUSDT"
BTC_TF = "4h"
FRED_SERIES = ("SP500", "VIXCLS", "DTWEXBGS")
