# tests/test_edge_exits.py
from __future__ import annotations

import unittest

from moonface.core.exits import (
    atr_trail,
    breakeven_horizon,
    donchian_trail,
    fixed_bracket,
    horizon_hold,
    horizon_wide_stop,
)
from moonface.core.models import Candle

_HOUR = 3_600_000
_AP = {"atr_period": 14}


def _series(path: list[tuple[float, float, float]], warmup_close: float = 100.0,
            n_warmup: int = 15) -> list[Candle]:
    """n_warmup flat bars (high=close+0.5, low=close-0.5 -> ATR=1.0 over period 14),
    then the supplied path. Entry index is n_warmup - 1; entry close == warmup_close;
    the 1xATR R unit is exactly 1.0. path items are (high, low, close)."""
    bars: list[tuple[float, float, float]] = [
        (warmup_close + 0.5, warmup_close - 0.5, warmup_close) for _ in range(n_warmup)
    ]
    bars.extend(path)
    return [Candle(i * _HOUR, c, hi, lo, c, 1.0) for i, (hi, lo, c) in enumerate(bars)]


_ENTRY = 14  # n_warmup - 1


class HorizonHoldTest(unittest.TestCase):
    def test_marks_to_close_at_horizon(self) -> None:
        h1 = _series([(101, 100, 101), (103, 102, 102)])  # close at i+2 == 102
        params = {"n_bars": 2, **_AP}
        self.assertEqual(horizon_hold(_ENTRY, "LONG", h1, params), 2.0)

    def test_short_is_signed(self) -> None:
        h1 = _series([(101, 100, 101), (103, 102, 102)])
        params = {"n_bars": 2, **_AP}
        self.assertEqual(horizon_hold(_ENTRY, "SHORT", h1, params), -2.0)


class HorizonWideStopTest(unittest.TestCase):
    def test_stop_hit_returns_negative_k_stop(self) -> None:
        h1 = _series([(100, 97, 98)])  # low 97 <= stop 97.5
        params = {"n_bars": 24, "k_stop": 2.5, **_AP}
        self.assertEqual(horizon_wide_stop(_ENTRY, "LONG", h1, params), -2.5)

    def test_no_stop_marks_to_close(self) -> None:
        h1 = _series([(100.5, 99.5, 100), (102.5, 101.5, 102)])
        params = {"n_bars": 2, "k_stop": 2.5, **_AP}
        self.assertEqual(horizon_wide_stop(_ENTRY, "LONG", h1, params), 2.0)

    def test_lookahead_safe_after_exit(self) -> None:
        h1 = _series([(100, 97, 98), (101, 100, 100), (101, 100, 100),
                      (101, 100, 100), (101, 100, 100)])
        params = {"n_bars": 24, "k_stop": 2.5, **_AP}
        baseline = horizon_wide_stop(_ENTRY, "LONG", h1, params)
        h1[_ENTRY + 4] = Candle(h1[_ENTRY + 4].timestamp_ms, 100, 9999, 100, 100, 1.0)
        self.assertEqual(horizon_wide_stop(_ENTRY, "LONG", h1, params), baseline)

    def test_entry_on_last_bar_is_none(self) -> None:
        h1 = _series([])  # entry index 14 == len-1
        params = {"n_bars": 24, "k_stop": 2.5, **_AP}
        self.assertIsNone(horizon_wide_stop(_ENTRY, "LONG", h1, params))


class FixedBracketTest(unittest.TestCase):
    def test_take_profit_hit(self) -> None:
        h1 = _series([(104, 100, 103)])  # high 104 >= tp 104, low 100 > stop 99
        params = {"k_stop": 1.0, "m_tp": 4.0, **_AP}
        self.assertEqual(fixed_bracket(_ENTRY, "LONG", h1, params), 4.0)

    def test_stop_hit(self) -> None:
        h1 = _series([(101, 99, 100)])  # low 99 <= stop 99
        params = {"k_stop": 1.0, "m_tp": 4.0, **_AP}
        self.assertEqual(fixed_bracket(_ENTRY, "LONG", h1, params), -1.0)

    def test_pessimistic_stop_before_tp_same_bar(self) -> None:
        h1 = _series([(104, 99, 101)])  # both touched -> stop fills first
        params = {"k_stop": 1.0, "m_tp": 4.0, **_AP}
        self.assertEqual(fixed_bracket(_ENTRY, "LONG", h1, params), -1.0)

    def test_short_symmetry(self) -> None:
        h1 = _series([(100, 96, 97)])  # high 100 < stop 101; low 96 <= tp 96
        params = {"k_stop": 1.0, "m_tp": 4.0, **_AP}
        self.assertEqual(fixed_bracket(_ENTRY, "SHORT", h1, params), 4.0)


class AtrTrailTest(unittest.TestCase):
    def test_trails_up_then_stops_out_in_profit(self) -> None:
        # bar1 runs to 110 (extreme 110 -> stop 108); bar2 low 107 <= 108 -> fill 108.
        h1 = _series([(110, 100, 110), (110, 107, 108)])
        params = {"k_trail": 2.0, "max_bars": 48, **_AP}
        self.assertEqual(atr_trail(_ENTRY, "LONG", h1, params), 8.0)

    def test_immediate_stop(self) -> None:
        h1 = _series([(100, 97, 98)])  # initial stop 98; low 97 <= 98
        params = {"k_trail": 2.0, "max_bars": 48, **_AP}
        self.assertEqual(atr_trail(_ENTRY, "LONG", h1, params), -2.0)


class DonchianTrailTest(unittest.TestCase):
    """Reproduces trend_sim._run_position: initial k_stop*ATR stop, then trail
    by the prior trail_n channel extreme (ratcheted toward price), gross R."""

    def test_channel_trail_locks_in_profit(self) -> None:
        # warmup lows are 99.5; the prior-2 channel ratchets the stop up to 105
        # by bar i+3, whose low (104) then touches it -> exit at 105 -> +5R.
        h1 = _series([(110, 105, 110), (112, 108, 111), (111, 104, 106)])
        params = {"k_stop": 2.0, "trail_n": 2, **_AP}
        self.assertEqual(donchian_trail(_ENTRY, "LONG", h1, params), 5.0)

    def test_initial_stop_governs_when_channel_is_below(self) -> None:
        # k_stop 0.25 -> initial stop 99.75 sits above the 99.5 warmup channel,
        # so the initial stop is what bar i+1's low (99.6) touches -> -0.25R.
        h1 = _series([(100, 99.6, 99.7)])
        params = {"k_stop": 0.25, "trail_n": 2, **_AP}
        self.assertEqual(donchian_trail(_ENTRY, "LONG", h1, params), -0.25)

    def test_marks_to_close_when_never_stopped(self) -> None:
        # trail_n 20 > available history, so the channel never tightens the stop;
        # price drifts up and is marked to the final close (+0.5R).
        h1 = _series([(100.5, 99.5, 100), (100.6, 99.6, 100.5)])
        params = {"k_stop": 2.0, "trail_n": 20, **_AP}
        self.assertEqual(donchian_trail(_ENTRY, "LONG", h1, params), 0.5)

    def test_short_symmetry(self) -> None:
        # mirror of the long case: prior-2 channel high ratchets the stop down to
        # 95, bar i+3's high (96) touches it -> short profit (100-95)/1 = +5R.
        h1 = _series([(95, 90, 90), (92, 88, 89), (96, 91, 94)])
        params = {"k_stop": 2.0, "trail_n": 2, **_AP}
        self.assertEqual(donchian_trail(_ENTRY, "SHORT", h1, params), 5.0)


class DeployExitRegistryTest(unittest.TestCase):
    def test_donchian_trail_is_executable_but_not_a_research_exit(self) -> None:
        # Deployment-only: a promoted strategy may name it and the forward gate
        # executes it, but it must stay out of the research search set so it
        # never changes a pre-registered grid's DSR calibration.
        from moonface.core.exits import (DEPLOY_EXIT_REGISTRY,
                                                  EXECUTABLE_EXITS,
                                                  EXIT_REGISTRY)
        from moonface.core.metrics import _EXIT_FNS as EXIT_FNS
        self.assertIn("donchian_trail", DEPLOY_EXIT_REGISTRY)
        self.assertIn("donchian_trail", EXECUTABLE_EXITS)
        self.assertIn("donchian_trail", EXIT_FNS)
        self.assertNotIn("donchian_trail", EXIT_REGISTRY)


class BreakevenHorizonTest(unittest.TestCase):
    def test_arms_at_plus_1r_then_breakeven_stop(self) -> None:
        # bar1 high 101.5 reaches +1R (target 101) -> stop moves to entry 100;
        # bar2 low 99 <= 100 -> fill at breakeven -> R 0.
        h1 = _series([(101.5, 100, 101), (100.5, 99, 100)])
        params = {"n_bars": 24, "k_stop": 3.0, **_AP}
        self.assertEqual(breakeven_horizon(_ENTRY, "LONG", h1, params), 0.0)

    def test_never_arms_marks_to_close(self) -> None:
        h1 = _series([(100.5, 99.5, 100), (100.8, 99.5, 100.5)])  # never >= 101
        params = {"n_bars": 2, "k_stop": 3.0, **_AP}
        self.assertEqual(breakeven_horizon(_ENTRY, "LONG", h1, params), 0.5)