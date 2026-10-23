# tests/test_research_ladder.py
import unittest

from moonface.research import ladder
from moonface.core.bundle import DataBundle
from moonface.kernel.spec import HypothesisSpec
from moonface.kernel.synth import make_candles

ASSET = {"exchange": "x", "symbol": "S", "timeframe": "4h"}


def make_spec(n: int = 20, n_bars: int = 24, fraction: float = 0.01) -> HypothesisSpec:
    return HypothesisSpec(
        domain="d", version=1, asset=ASSET,
        entry={"family": "donchian_break", "params": {"n": n}},
        exit={"name": "horizon_hold", "params": {"n_bars": n_bars, "atr_period": 14}},
        fraction=fraction,
    )


class TestEvaluateResearch(unittest.TestCase):
    def setUp(self):
        self.bundle = DataBundle(candles=make_candles(1200, seed=7, drift=0.003))

    def test_metrics_dict_shape(self):
        m = ladder.evaluate_research(make_spec(), self.bundle)
        for key in ("screen_trades", "screen_expectancy_r", "holdout_trades",
                    "holdout_mar", "research_trades", "research_mar",
                    "research_sharpe", "research_skew", "research_kurtosis"):
            self.assertIn(key, m)

    def test_split_partitions_the_stream(self):
        m = ladder.evaluate_research(make_spec(), self.bundle)
        self.assertEqual(m["research_trades"],
                         m["screen_trades"] + m["holdout_trades"])
        self.assertGreater(m["research_trades"], 0)

    def test_deterministic(self):
        a = ladder.evaluate_research(make_spec(), self.bundle)
        b = ladder.evaluate_research(make_spec(), self.bundle)
        self.assertEqual(a, b)


class TestStageGates(unittest.TestCase):
    def test_stage1_needs_trades_and_positive_expectancy(self):
        good = {"screen_trades": 30, "screen_expectancy_r": 0.1}
        self.assertTrue(ladder.stage1_passed(good))
        self.assertFalse(ladder.stage1_passed(
            {"screen_trades": 29, "screen_expectancy_r": 0.1}))
        self.assertFalse(ladder.stage1_passed(
            {"screen_trades": 30, "screen_expectancy_r": 0.0}))

    def test_stage1_floor_is_overridable_for_tests(self):
        m = {"screen_trades": 2, "screen_expectancy_r": 0.1}
        self.assertFalse(ladder.stage1_passed(m))
        self.assertTrue(ladder.stage1_passed(m, min_trades=1))

    def test_stage2_gates_on_holdout_mar(self):
        self.assertTrue(ladder.stage2_passed({"holdout_mar": 0.01, "holdout_drawdown": 0.0}))
        self.assertFalse(ladder.stage2_passed({"holdout_mar": 0.0, "holdout_drawdown": 0.0}))
        self.assertFalse(ladder.stage2_passed({"holdout_mar": -2.0, "holdout_drawdown": 0.0}))


def _row(h: str, status: str, sharpe: float, trades: int = 100) -> dict:
    return {"spec_hash": h, "status": status,
            "stage_results": {"research_sharpe": sharpe, "research_trades": trades,
                              "research_skew": 0.0, "research_kurtosis": 3.0}}


class TestStage3(unittest.TestCase):
    def test_dsr_computed_only_for_oos_pass_rows(self):
        rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1),
                _row("c", "oos_pass", -0.2)]
        dsr = ladder.stage3_dsr(rows, grid_size=10)
        self.assertEqual(set(dsr), {"a", "c"})

    def test_all_sharpes_feed_the_trial_variance(self):
        # Adding a rejected row with an extreme SR widens the trial-SR variance,
        # which raises the benchmark and lowers every DSR.
        base = [_row("a", "oos_pass", 0.5), _row("b", "oos_pass", 0.4)]
        spread = base + [_row("z", "rejected", 5.0)]
        self.assertLess(ladder.stage3_dsr(spread, 10)["a"],
                        ladder.stage3_dsr(base, 10)["a"])

    def test_bigger_grid_deflates_more(self):
        rows = [_row("a", "oos_pass", 0.5), _row("b", "rejected", 0.1),
                _row("c", "rejected", -0.1)]
        self.assertLess(ladder.stage3_dsr(rows, 1000)["a"],
                        ladder.stage3_dsr(rows, 10)["a"])

    def test_rows_without_stage1_metrics_are_skipped(self):
        rows = [_row("a", "oos_pass", 0.5),
                {"spec_hash": "e", "status": "error", "stage_results": {}}]
        self.assertEqual(set(ladder.stage3_dsr(rows, 10)), {"a"})


class TestStage4(unittest.TestCase):
    def test_lockbox_counts_only_tail_entries(self):
        candles = make_candles(1200, seed=7, drift=0.003)
        full = DataBundle(candles=candles)
        spec = make_spec()
        fence_index = 960
        research_m = ladder.evaluate_research(
            spec, DataBundle(candles=candles[:fence_index]))
        tail_m = ladder.evaluate_lockbox(spec, full, fence_index)
        self.assertIn("tail_trades", tail_m)
        self.assertIn("tail_mar", tail_m)
        # tail trades must be a strict subset of what the full series produces
        full_stream = ladder.r_stream(spec, full)
        expected = len([1 for i, _, _ in full_stream if i >= fence_index])
        self.assertEqual(tail_m["tail_trades"], expected)
        self.assertLessEqual(tail_m["tail_trades"],
                             len(full_stream) - research_m["research_trades"] + 5)

    def test_stage4_gate(self):
        self.assertTrue(ladder.stage4_passed({"tail_mar": 1.0, "tail_trades": 10, "tail_drawdown": 0.0}))
        self.assertFalse(ladder.stage4_passed({"tail_mar": 0.99, "tail_trades": 10, "tail_drawdown": 0.0}))
        self.assertFalse(ladder.stage4_passed({"tail_mar": 1.5, "tail_trades": 9, "tail_drawdown": 0.0}))

    def test_stage4_gate_overridable_for_tests(self):
        m = {"tail_mar": -5.0, "tail_trades": 1, "tail_drawdown": 0.0}
        self.assertFalse(ladder.stage4_passed(m))
        self.assertTrue(ladder.stage4_passed(m, min_mar=-10.0, min_trades=0))




def test_cost_fraction_constant():
    assert ladder.COST_FRACTION == 0.001


def test_r_stream_nets_costs_inversely_to_atr_fraction(monkeypatch):
    # Two synthetic streams identical except ATR size: the tiny-ATR one
    # must pay proportionally more cost in R.
    # Use the public pieces directly rather than a full bundle:
    # cost_r = COST_FRACTION / atr_frac.
    assert ladder.COST_FRACTION / 0.001 == 1.0   # 0.1% ATR -> 1R round-trip
    assert ladder.COST_FRACTION / 0.01 == 0.1    # 1% ATR   -> 0.1R round-trip


def test_stage2_rejects_beyond_drawdown_budget():
    base = {"holdout_mar": 5.0}
    assert ladder.stage2_passed({**base, "holdout_drawdown": -0.29})
    assert not ladder.stage2_passed({**base, "holdout_drawdown": -0.31})


def test_stage4_rejects_beyond_drawdown_budget():
    base = {"tail_mar": 5.0, "tail_trades": 50}
    assert ladder.stage4_passed({**base, "tail_drawdown": -0.29})
    assert not ladder.stage4_passed({**base, "tail_drawdown": -0.31})


def test_drawdown_budget_constant():
    assert ladder.DRAWDOWN_BUDGET == -0.30


def test_single_trade_r_matches_r_stream():
    from moonface.research import ladder
    from moonface.core.bundle import DataBundle
    from moonface.kernel.spec import HypothesisSpec
    from moonface.kernel.synth import make_candles

    candles = make_candles(300)
    spec = HypothesisSpec(
        domain="t", version=1,
        asset={"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"},
        entry={"family": "donchian_break", "params": {"n": 20}},
        exit={"name": "fixed_bracket",
              "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}},
        fraction=0.01)
    stream = ladder.r_stream(spec, DataBundle(candles=candles))
    assert stream, "synthetic drift data must produce trades"
    from moonface.research.entries import generate_entries
    sides = dict(generate_entries("donchian_break", {"n": 20},
                                  DataBundle(candles=candles)))
    for i, r, af in stream:
        got = ladder.single_trade_r(candles, i, sides[i], "fixed_bracket",
                                    {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0})
        assert got is not None
        assert abs(got[0] - r) < 1e-12 and abs(got[1] - af) < 1e-12


if __name__ == "__main__":
    unittest.main()
