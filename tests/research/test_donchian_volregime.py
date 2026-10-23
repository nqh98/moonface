import unittest
from dataclasses import dataclass

from moonface.research.donchian_volregime import features as F
from moonface.research.donchian_volregime.evaluate import gate
from moonface.research.donchian_volregime.grid import CELLS, CFG, N_TRIALS
from moonface.research.donchian_volregime.llm_gate import (
    combine,
    rationale_is_clean,
)
from moonface.research.donchian_volregime.select import (
    INACTIVE,
    NEGATIVE,
    PAPER_CANDIDATE,
    sealed_verdict,
    select_cell,
)


@dataclass
class C:
    high: float
    low: float
    close: float


@dataclass
class T:
    entry_index: int
    r_multiple: float


def _ramp(n, base_range=1.0, close0=100.0):
    """n candles with constant range and a rising close."""
    out = []
    close = close0
    for _ in range(n):
        out.append(C(high=close + base_range, low=close - base_range, close=close))
        close += 0.5
    return out


class TestFeatures(unittest.TestCase):
    def test_atr_series_zero_during_warmup_then_mean_tr(self):
        candles = [C(10, 8, 9), C(11, 9, 10), C(12, 10, 11), C(13, 11, 12)]
        atr = F.atr_series(candles, 2)
        self.assertEqual(atr[0], 0.0)  # need 2 TR values
        self.assertGreater(atr[2], 0.0)
        self.assertEqual(len(atr), 4)

    def test_rolling_percentile_none_before_window_and_bounds(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertIsNone(F.rolling_percentile(vals, 2, 4))
        self.assertEqual(F.rolling_percentile(vals, 3, 4), 1.0)  # 4 is the max in [1..4]
        self.assertAlmostEqual(F.rolling_percentile(vals, 4, 4), 1.0)  # 5 is max in [2..5]

    def test_allow_flags_no_lookahead_all_bool(self):
        candles = _ramp(300)
        for cell in CELLS:
            flags = F.allow_flags(candles, cell, CFG)
            self.assertEqual(len(flags), len(candles))
            self.assertTrue(all(isinstance(x, bool) for x in flags))
            # warm-up bar 0 can never be allowed (no history)
            self.assertFalse(flags[0])

    def test_expansion_flag_true_when_short_atr_exceeds_long(self):
        # rising true range -> short ATR > long ATR -> expansion allowed late
        candles = []
        close = 100.0
        rng = 1.0
        for _ in range(160):
            candles.append(C(close + rng, close - rng, close))
            close += 0.2
            rng *= 1.01  # widening range => expansion
        flags = F.allow_flags(candles, "expansion", CFG)
        self.assertTrue(flags[-1])


class TestGate(unittest.TestCase):
    def test_gate_keeps_only_allowed_entry_bars(self):
        base = [T(0, 1.0), T(1, -1.0), T(2, 2.0)]
        flags = [True, False, True]
        kept = gate(base, flags)
        self.assertEqual([t.entry_index for t in kept], [0, 2])


class TestSelect(unittest.TestCase):
    def test_select_cell_picks_least_negative_dd_qualifier(self):
        rows = [
            {"cell": "a", "qualifies": True,
             "gated": {"max_dd_r": -5.0, "net_r": 10.0}, "robust_frac": 0.8},
            {"cell": "b", "qualifies": True,
             "gated": {"max_dd_r": -3.0, "net_r": 8.0}, "robust_frac": 0.9},
            {"cell": "c", "qualifies": False,
             "gated": {"max_dd_r": -1.0, "net_r": 20.0}, "robust_frac": 1.0},
        ]
        self.assertEqual(select_cell(rows), "b")

    def test_select_cell_none_when_no_qualifier(self):
        rows = [{"cell": "a", "qualifies": False,
                 "gated": {"max_dd_r": -1.0, "net_r": 5.0}, "robust_frac": 1.0}]
        self.assertIsNone(select_cell(rows))

    def test_sealed_verdict_paper_candidate_requires_net_positive(self):
        base = {"n": 30, "net_r": -10.0, "profit_factor": 0.5, "max_dd_r": -15.0}
        good = {"n": 20, "net_r": 5.0, "profit_factor": 1.4, "max_dd_r": -8.0}
        self.assertEqual(sealed_verdict(base, good), PAPER_CANDIDATE)

    def test_sealed_verdict_negative_when_less_bad_but_still_losing(self):
        base = {"n": 30, "net_r": -10.0, "profit_factor": 0.5, "max_dd_r": -15.0}
        lessbad = {"n": 17, "net_r": -9.0, "profit_factor": 0.25, "max_dd_r": -11.0}
        self.assertEqual(sealed_verdict(base, lessbad), NEGATIVE)

    def test_sealed_verdict_inactive_when_too_few_trades(self):
        base = {"n": 30, "net_r": -10.0, "profit_factor": 0.5, "max_dd_r": -15.0}
        thin = {"n": 4, "net_r": 3.0, "profit_factor": 2.0, "max_dd_r": -1.0}
        self.assertEqual(sealed_verdict(base, thin), INACTIVE)


class TestGridFrozen(unittest.TestCase):
    def test_five_cells(self):
        self.assertEqual(N_TRIALS, 5)
        self.assertIn("hivol_expansion", CELLS)


class TestLlmGate(unittest.TestCase):
    def test_veto_forces_wait(self):
        self.assertEqual(combine(True, "LONG", "veto")["action"], "WAIT")

    def test_uncertain_forces_wait(self):
        self.assertEqual(combine(True, "LONG", "uncertain")["action"], "WAIT")

    def test_allow_passes_long_only_if_quant_allows(self):
        self.assertEqual(combine(True, "LONG", "allow"),
                         {"action": "LONG", "size_mult": 1.0})
        self.assertEqual(combine(False, "LONG", "allow")["action"], "WAIT")

    def test_reduce_risk_halves_size(self):
        self.assertEqual(combine(True, "LONG", "reduce_risk"),
                         {"action": "LONG", "size_mult": 0.5})

    def test_wait_action_stays_wait_even_when_allowed(self):
        self.assertEqual(combine(True, "WAIT", "allow")["action"], "WAIT")

    def test_llm_never_creates_short(self):
        # SHORT is not a valid Donchian action here; only LONG/WAIT permitted.
        with self.assertRaises(ValueError):
            combine(True, "SHORT", "allow")

    def test_rationale_guard_rejects_directional_tokens(self):
        self.assertFalse(rationale_is_clean("macro risk-off, suggest a short"))
        self.assertTrue(rationale_is_clean("liquidity contracting; elevated macro risk"))


if __name__ == "__main__":
    unittest.main()
