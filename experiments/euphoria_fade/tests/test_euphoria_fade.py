"""Hermetic tests for the euphoria_fade v1 registered lane."""
import unittest

from euphoria_fade_backtest import WINDOWS, _ms, gen_entries


class GenEntriesTest(unittest.TestCase):
    def test_p1_fires_once_per_episode(self):
        f = [False, True, True, False, True]
        self.assertEqual(gen_entries(f, 1), [1, 4])

    def test_p2_requires_two_consecutive_bars(self):
        f = [False, True, True, True, False, True, False]
        self.assertEqual(gen_entries(f, 2), [2])

    def test_series_starting_in_cell_never_fires(self):
        self.assertEqual(gen_entries([True, True, True], 1), [])
        self.assertEqual(gen_entries([True, True, True], 2), [])

    def test_empty_and_all_false(self):
        self.assertEqual(gen_entries([], 1), [])
        self.assertEqual(gen_entries([False] * 5, 1), [])


class WindowsTest(unittest.TestCase):
    def test_windows_are_contiguous_and_frozen(self):
        self.assertEqual(WINDOWS["IS"], (_ms("2020-01-01"), _ms("2024-01-01")))
        self.assertEqual(WINDOWS["OOS"][1], WINDOWS["LOCKBOX"][0])
        self.assertEqual(WINDOWS["LOCKBOX"][1], _ms("2026-07-01"))


from moonface.foundation.models import Candle

from euphoria_fade_backtest import Trade, simulate_symbol

TS0 = 1_600_000_000_000
STEP = 14_400_000


def bars(specs):
    """specs: list of (open, high, low, close)."""
    return [Candle(timestamp_ms=TS0 + i * STEP, open=o, high=h, low=l,
                   close=c, volume=1.0)
            for i, (o, h, l, c) in enumerate(specs)]


FLAT = (100.0, 101.0, 99.0, 100.0)   # TR = 2 vs prev close 100 -> ATR = 2
# With ATR=2 at the signal bar: entry=100.0, risk=K_STOP*2=4.0,
# stop=104.0, tp=100-1*2=98.0, cost_r = 0.0006*100/4 = 0.015.


class SimulateShortTest(unittest.TestCase):
    def test_tp_hit(self):
        candles = bars([FLAT] * 21 + [(100.0, 101.0, 97.0, 98.0)])
        trades = simulate_symbol("X", candles, [19])
        self.assertEqual(len(trades), 1)
        t = trades[0]
        self.assertEqual(t.outcome, "tp")
        self.assertEqual(t.entry_ts, TS0 + 20 * STEP)
        self.assertAlmostEqual(t.entry, 100.0)
        self.assertAlmostEqual(t.risk, 4.0)
        self.assertAlmostEqual(t.r_gross, 0.5)
        self.assertAlmostEqual(t.r_net, 0.485)

    def test_stop_hit(self):
        candles = bars([FLAT] * 21 + [(100.0, 105.0, 99.0, 104.0)])
        t = simulate_symbol("X", candles, [19])[0]
        self.assertEqual(t.outcome, "stop")
        self.assertAlmostEqual(t.r_gross, -1.0)
        self.assertAlmostEqual(t.r_net, -1.015)

    def test_stop_first_tie_break(self):
        candles = bars([FLAT] * 21 + [(100.0, 105.0, 97.0, 100.0)])
        t = simulate_symbol("X", candles, [19])[0]
        self.assertEqual(t.outcome, "stop")

    def test_end_of_data_flagged(self):
        candles = bars([FLAT] * 22)
        t = simulate_symbol("X", candles, [19])[0]
        self.assertEqual(t.outcome, "eod")
        self.assertAlmostEqual(t.r_gross, 0.0)
        self.assertAlmostEqual(t.r_net, -0.015)

    def test_no_overlapping_positions(self):
        specs = [FLAT] * 22 + [(100.0, 101.0, 97.0, 98.0)] + [FLAT] * 3
        trades = simulate_symbol("X", bars(specs), [19, 21])
        self.assertEqual(len(trades), 1)      # 2nd fill bar 22 == busy bar

    def test_signal_at_last_bar_is_skipped(self):
        candles = bars([FLAT] * 21)
        self.assertEqual(simulate_symbol("X", candles, [20]), [])


from euphoria_fade_backtest import (dsr_of, equity_stats, expectancy, mar,
                                    partition)


def stub_trade(entry_ts, r_net=0.1):
    return Trade("X", entry_ts - STEP, entry_ts, 100.0, 4.0, r_net, r_net,
                 "tp")


class MetricsTest(unittest.TestCase):
    def test_expectancy(self):
        self.assertEqual(expectancy([]), 0.0)
        self.assertAlmostEqual(expectancy([1.0, -0.5]), 0.25)

    def test_equity_stats_known_path(self):
        total, dd = equity_stats([1.0, -1.0], f=0.01)
        self.assertAlmostEqual(total, 1.01 * 0.99 - 1.0)
        self.assertAlmostEqual(dd, 0.99 - 1.0, places=6)

    def test_mar_zero_dd(self):
        self.assertEqual(mar([1.0, 1.0]), float("inf"))
        self.assertEqual(mar([]), 0.0)

    def test_dsr_separates_signal_from_noise(self):
        strong = [0.5, 0.4] * 20
        noise = [0.5, -0.5] * 20
        self.assertGreater(dsr_of(strong, [10.0]), 0.95)
        self.assertLess(dsr_of(noise, [0.0]), 0.6)
        self.assertEqual(dsr_of([0.1], [0.0]), 0.0)

    def test_partition_by_entry_ts(self):
        trades = [stub_trade(_ms("2021-06-01")),
                  stub_trade(_ms("2024-06-01")),
                  stub_trade(_ms("2025-08-01")),
                  stub_trade(_ms("2026-06-30"))]
        part = partition(trades)
        self.assertEqual([len(part[w]) for w in ("IS", "OOS", "LOCKBOX")],
                         [1, 1, 2])


from euphoria_fade_backtest import null_gate, run_null


class NullGateTest(unittest.TestCase):
    def test_strong_signal_passes(self):
        is_rs = [0.5, 0.4] * 20
        oos_rs = [0.5, 0.4] * 10
        self.assertTrue(null_gate(is_rs, oos_rs))

    def test_underpowered_or_flat_fails(self):
        self.assertFalse(null_gate([0.5] * 10, [0.5] * 10))       # n_IS < 30
        self.assertFalse(null_gate([0.5, -0.5] * 20, [0.0] * 10))  # flat OOS


class RunNullTest(unittest.TestCase):
    def _setup(self):
        candles = bars([FLAT] * 120)
        ts = [c.timestamp_ms for c in candles]
        cmaps = {"X": {t: k for k, t in enumerate(ts)}}
        elig = {"X": {"IS": list(range(20, 100)), "OOS": [], "LOCKBOX": []}}
        counts = {"X": {"IS": 5, "OOS": 0}}
        return {"X": candles}, cmaps, ts, elig, counts

    def test_deterministic_and_count_matched(self):
        args = self._setup()
        a = run_null(*args, seed=7, n_draws=5)
        b = run_null(*args, seed=7, n_draws=5)
        self.assertEqual(a["exps"], b["exps"])
        self.assertEqual(len(a["exps"]), 5)
        self.assertEqual(a["pass_rate"], 0.0)

    def test_count_capped_at_pool_size(self):
        candles_by_sym, cmaps, ts, elig, _ = self._setup()
        counts = {"X": {"IS": 999, "OOS": 0}}
        out = run_null(candles_by_sym, cmaps, ts, elig, counts, seed=1,
                       n_draws=2)
        self.assertEqual(len(out["exps"]), 2)


from euphoria_fade_backtest import (assemble_verdict, render_report, stage1,
                                    stage2, stage4, stage5)

STRONG = [0.5, 0.4] * 20            # n=40, exp=0.45, tiny variance
WEAK = [0.5, -0.5] * 20             # n=40, exp=0


def cellset(treat_is, treat_oos, ctrl_oos, lb=None, ctrl_lb=None):
    return {"treat": {"IS": treat_is, "OOS": treat_oos,
                      "LOCKBOX": lb or []},
            "ctrl": {"IS": [], "OOS": ctrl_oos, "LOCKBOX": ctrl_lb or []}}


class StagesTest(unittest.TestCase):
    def test_stage1(self):
        self.assertTrue(stage1(STRONG))
        self.assertFalse(stage1([0.5] * 29))
        self.assertFalse(stage1(WEAK))

    def test_stage2_requires_dominance(self):
        self.assertTrue(stage2(STRONG, WEAK))
        self.assertFalse(stage2(STRONG, [0.9] * 40))
        self.assertFalse(stage2(WEAK, [-1.0] * 40))   # exp 0 not > 0

    def test_stage4(self):
        nulls = [i * 0.001 - 0.1 for i in range(200)]   # p95 ~ 0.09
        self.assertTrue(stage4(0.45, nulls, 0.0))
        self.assertFalse(stage4(0.45, nulls, 0.10))    # null passes gate
        self.assertFalse(stage4(0.05, nulls, 0.0))     # below p95
        self.assertFalse(stage4(0.45, [], 0.0))

    def test_stage5(self):
        self.assertTrue(stage5(STRONG[:20], WEAK[:20]))
        self.assertFalse(stage5(STRONG[:19], WEAK[:19]))   # n < 20


class VerdictTest(unittest.TestCase):
    def _nulls(self, pass_rate=0.0):
        return {p: {"exps": [i * 0.001 - 0.1 for i in range(200)],
                    "pass_rate": pass_rate} for p in (1, 2)}

    def test_pending_lockbox_when_one_cell_clears(self):
        cells = {1: cellset(STRONG, STRONG[:30], WEAK[:30]),
                 2: cellset(WEAK, WEAK[:30], WEAK[:30])}
        v = assemble_verdict(cells, self._nulls())
        self.assertEqual(v["verdict"], "PENDING_LOCKBOX")
        self.assertEqual(v["pending_cells"], [1])
        self.assertTrue(v["cells"][1]["pass_1_4"])
        self.assertFalse(v["cells"][2]["pass_1_4"])

    def test_all_fail_is_closed_negative(self):
        cells = {p: cellset(WEAK, WEAK[:30], WEAK[:30]) for p in (1, 2)}
        v = assemble_verdict(cells, self._nulls())
        self.assertEqual(v["verdict"], "CLOSED_NEGATIVE")

    def test_null_passing_gate_voids_lane(self):
        cells = {1: cellset(STRONG, STRONG[:30], WEAK[:30]),
                 2: cellset(WEAK, WEAK[:30], WEAK[:30])}
        v = assemble_verdict(cells, self._nulls(pass_rate=0.5))
        self.assertEqual(v["verdict"], "GATE_VOID_NULL_PASSES")

    def test_report_renders_and_never_leaks_lockbox_stats(self):
        cells = {p: cellset(WEAK, WEAK[:30], WEAK[:30],
                            lb=[9.9] * 25, ctrl_lb=[9.9] * 25)
                 for p in (1, 2)}
        v = assemble_verdict(cells, self._nulls())
        text = render_report(v)
        self.assertIn("CLOSED_NEGATIVE", text)
        self.assertNotIn("9.9", text)


import json as _json
from pathlib import Path

from euphoria_fade_backtest import execute_run
from tests.helpers_microscope import make_pool


class ExecuteRunTest(unittest.TestCase):
    def test_smoke_deterministic_and_sealed(self):
        import tempfile
        pool = make_pool(n=400, n_assets=10, seed=3)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            v1 = execute_run(pool, seed=1, out_dir=out)
            j1 = (out / "run_verdict.json").read_text()
            self.assertIn(v1["verdict"],
                          ("CLOSED_NEGATIVE", "PENDING_LOCKBOX",
                           "GATE_VOID_NULL_PASSES"))
            self.assertTrue((out / "run_report.md").exists())
            sealed = _json.loads((out / "lockbox_trades.json").read_text())
            self.assertEqual(set(sealed), {"1", "2"})
            self.assertEqual(set(sealed["1"]), {"treat", "ctrl"})
            # verdict never leaks lockbox stats: exact per-cell key set
            expected_keys = {"stage1", "stage2", "stage3", "stage4", "dsr",
                             "n_is", "n_oos", "exp_is", "exp_oos",
                             "exp_ctrl_oos", "null_pass_rate", "pass_1_4"}
            for s in _json.loads(j1)["cells"].values():
                self.assertEqual(set(s), expected_keys)
            v2 = execute_run(pool, seed=1, out_dir=out)
            self.assertEqual(v1["cells"], v2["cells"])

    def test_collapsed_pool_aborts(self):
        pool = make_pool(n=400, n_assets=10, seed=3)
        small = {k: pool[k] for k in list(pool)[:3]}
        with self.assertRaises(SystemExit):
            execute_run(small, seed=1, out_dir=Path("/nonexistent-unused"))


from euphoria_fade_backtest import run_lockbox


class LockboxTest(unittest.TestCase):
    def _prepare(self, td, verdict="PENDING_LOCKBOX", pending=(1,),
                 lb=None, ctrl_lb=None):
        out = Path(td)
        (out / "run_verdict.json").write_text(_json.dumps(
            {"verdict": verdict, "pending_cells": list(pending),
             "cells": {}, "seed": 1}))
        sealed = {str(p): {"treat": lb if lb is not None else [0.5] * 25,
                           "ctrl": ctrl_lb if ctrl_lb is not None
                           else [-0.1] * 25}
                  for p in (1, 2)}
        (out / "lockbox_trades.json").write_text(_json.dumps(sealed))
        return out

    def test_refuses_without_ack(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = self._prepare(td)
            self.assertIn("REFUSED", run_lockbox(out, ack=False))
            self.assertFalse((out / "lockbox_result.json").exists())

    def test_refuses_when_nothing_pending(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = self._prepare(td, verdict="CLOSED_NEGATIVE", pending=())
            self.assertIn("REFUSED", run_lockbox(out, ack=True))

    def test_one_touch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = self._prepare(td)
            first = run_lockbox(out, ack=True)
            self.assertIn("FORWARD_PAPER_REGISTERED", first)
            self.assertTrue((out / "lockbox_result.json").exists())
            self.assertIn("REFUSED", run_lockbox(out, ack=True))

    def test_failing_lockbox_closes_negative(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = self._prepare(td, lb=[-0.2] * 25, ctrl_lb=[-0.5] * 25)
            self.assertIn("CLOSED_NEGATIVE", run_lockbox(out, ack=True))
