# tests/research/ls_tournament/test_exit_ablation.py
"""Unit tests for the exit-ablation lane's three NEW local exit functions.

These exits are deliberately kept OUT of the frozen EXIT_REGISTRY / EXECUTABLE_EXITS
(so DSR calibration on concluded domains is untouched); they exist only to ablate
the frozen donchian_break n=100 4h long/short survivor's exit management. The
fixture mirrors tests/test_edge_exits.py: 15 flat warmup bars give ATR==1.0 and
entry close==100, so one R == 1.0 price unit and gross R reads directly.
"""
from __future__ import annotations

import unittest

from moonface.core.exits import breakeven_horizon
from moonface.core.models import Candle
from moonface.research.ls_tournament.exit_ablation import (
    breakeven_r,
    lock_profit,
    partial_tp_trail,
)

_HOUR = 3_600_000
_AP = {"atr_period": 14}
_ENTRY = 14  # n_warmup - 1


def _series(path: list[tuple[float, float, float]], warmup_close: float = 100.0,
            n_warmup: int = 15) -> list[Candle]:
    bars: list[tuple[float, float, float]] = [
        (warmup_close + 0.5, warmup_close - 0.5, warmup_close) for _ in range(n_warmup)
    ]
    bars.extend(path)
    return [Candle(i * _HOUR, c, hi, lo, c, 1.0) for i, (hi, lo, c) in enumerate(bars)]


class BreakevenRTest(unittest.TestCase):
    def test_equivalent_to_breakeven_horizon_at_trigger_1(self) -> None:
        # +1R reached then pulled back to entry -> stop-at-entry -> R == 0.
        h1 = _series([(101, 100, 100.5), (100, 99.9, 99.95)])
        p = {"n_bars": 2, "k_stop": 2.0, "be_trigger": 1.0, **_AP}
        legacy = breakeven_horizon(_ENTRY, "LONG", h1, {"n_bars": 2, "k_stop": 2.0, **_AP})
        self.assertEqual(breakeven_r(_ENTRY, "LONG", h1, p), legacy)
        self.assertEqual(breakeven_r(_ENTRY, "LONG", h1, p), 0.0)

    def test_trigger_1_5_does_not_arm_at_plus_1r(self) -> None:
        # high 101.2 reaches +1R but NOT +1.5R: stop stays at -2R and is hit.
        h1 = _series([(101.2, 99.0, 101.0), (101.0, 97.9, 99.0)])
        p15 = {"n_bars": 2, "k_stop": 2.0, "be_trigger": 1.5, **_AP}
        p10 = {"n_bars": 2, "k_stop": 2.0, "be_trigger": 1.0, **_AP}
        self.assertEqual(breakeven_r(_ENTRY, "LONG", h1, p15), -2.0)   # never armed
        self.assertEqual(breakeven_r(_ENTRY, "LONG", h1, p10), 0.0)    # armed -> breakeven

    def test_short_is_signed(self) -> None:
        # mirror: short reaches +1R (low 99) then reverts to entry.
        h1 = _series([(100, 99, 99.5), (100.1, 100, 100.05)])
        p = {"n_bars": 2, "k_stop": 2.0, "be_trigger": 1.0, **_AP}
        self.assertEqual(breakeven_r(_ENTRY, "SHORT", h1, p), 0.0)


class LockProfitTest(unittest.TestCase):
    def test_locks_one_r_after_two_r_reached(self) -> None:
        h1 = _series([(102.5, 100.0, 102.0), (101.5, 100.5, 101.0)])
        p = {"n_bars": 2, "k_stop": 2.0, "lock_trigger": 2.0, "lock_level": 1.0, **_AP}
        self.assertEqual(lock_profit(_ENTRY, "LONG", h1, p), 1.0)

    def test_initial_stop_hit_before_trigger(self) -> None:
        h1 = _series([(101.0, 97.9, 98.0)])
        p = {"n_bars": 2, "k_stop": 2.0, "lock_trigger": 2.0, "lock_level": 1.0, **_AP}
        self.assertEqual(lock_profit(_ENTRY, "LONG", h1, p), -2.0)

    def test_marks_to_close_if_neither(self) -> None:
        h1 = _series([(101.0, 99.5, 100.5), (101.4, 100.0, 101.0)])
        p = {"n_bars": 2, "k_stop": 2.0, "lock_trigger": 2.0, "lock_level": 1.0, **_AP}
        self.assertEqual(lock_profit(_ENTRY, "LONG", h1, p), 1.0)  # final close 101 -> +1R


class PartialTpTrailTest(unittest.TestCase):
    def test_partial_booked_then_remainder_trails_out(self) -> None:
        # bar1 hits +2R TP (book 0.5*2R=1.0R), trail to 100; bar2 low<=100 -> remainder 0R.
        h1 = _series([(102.0, 101.0, 102.0), (101.0, 99.9, 100.0)])
        p = {"tp_level": 2.0, "tp_frac": 0.5, "k_trail": 2.0, "k_stop": 2.0,
             "max_bars": 5, **_AP}
        self.assertEqual(partial_tp_trail(_ENTRY, "LONG", h1, p), 1.0)

    def test_full_stop_before_tp(self) -> None:
        h1 = _series([(101.0, 97.9, 98.0)])
        p = {"tp_level": 2.0, "tp_frac": 0.5, "k_trail": 2.0, "k_stop": 2.0,
             "max_bars": 5, **_AP}
        self.assertEqual(partial_tp_trail(_ENTRY, "LONG", h1, p), -2.0)

    def test_short_partial_and_trail(self) -> None:
        h1 = _series([(99.0, 98.0, 98.0), (100.1, 99.0, 100.0)])
        p = {"tp_level": 2.0, "tp_frac": 0.5, "k_trail": 2.0, "k_stop": 2.0,
             "max_bars": 5, **_AP}
        # short books 0.5*2R=1.0R at 98, trail to 100; bar2 high 100.1>=100 -> remainder 0R
        self.assertEqual(partial_tp_trail(_ENTRY, "SHORT", h1, p), 1.0)


if __name__ == "__main__":
    unittest.main()
