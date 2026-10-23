"""Tests for the vrp_measure measurement lane.

See experiments/vrp_measure/SPEC.md. Descriptive accounting: no forecasting,
no optimization. All fixtures synthetic. No network anywhere.
"""
from __future__ import annotations

import unittest

from moonface.research.exogenous.deribit_dvol import DvolPoint
from tools.collect.vrp_fetch_dvol import check_cadence, drop_incomplete_tail

RES_MS = 43_200_000


def _pts(first_ts: int, n: int) -> list[DvolPoint]:
    return [DvolPoint(first_ts + i * RES_MS, 50.0, 51.0, 49.0, 50.5) for i in range(n)]


class TestDropIncompleteTail(unittest.TestCase):
    def test_drops_bar_still_forming(self):
        pts = _pts(1_000_000_000_000, 3)
        last = pts[-1].ts_ms
        kept = drop_incomplete_tail(pts, now_ms=last + RES_MS - 1, interval_ms=RES_MS)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[-1].ts_ms, last - RES_MS)

    def test_keeps_bar_exactly_complete(self):
        pts = _pts(1_000_000_000_000, 3)
        last = pts[-1].ts_ms
        kept = drop_incomplete_tail(pts, now_ms=last + RES_MS, interval_ms=RES_MS)
        self.assertEqual(len(kept), 3)

    def test_empty_input(self):
        self.assertEqual(drop_incomplete_tail([], now_ms=1, interval_ms=RES_MS), [])


class TestCheckCadence(unittest.TestCase):
    def test_contiguous_passes(self):
        check_cadence(_pts(1_000_000_000_000, 5), RES_MS)  # must not raise

    def test_gap_raises(self):
        pts = _pts(1_000_000_000_000, 5)
        del pts[2]
        with self.assertRaises(Exception) as ctx:
            check_cadence(pts, RES_MS)
        self.assertIn("step", str(ctx.exception))

    def test_too_few_points_raises(self):
        with self.assertRaises(Exception):
            check_cadence(_pts(1_000_000_000_000, 1), RES_MS)


import csv as _csv  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
from tempfile import TemporaryDirectory  # noqa: E402

from moonface.research.vrp_measure import (  # noqa: E402
    DVOL_INTERVAL_MS,
    HOUR_MS,
    GapError as VrpGapError,
    load_dvol,
    load_spot_closes,
)


def _write_dvol(path, first_ts, n, step=DVOL_INTERVAL_MS, skip=()):
    with open(path, "w", newline="") as fh:
        w = _csv.writer(fh)
        for i in range(n):
            if i in skip:
                continue
            ts = first_ts + i * step
            w.writerow([ts, 50.0 + i, 52.0, 48.0, 50.0 + i + 1])


def _write_spot(path, first_ts, n, skip=()):
    with open(path, "w", newline="") as fh:
        w = _csv.writer(fh)
        for i in range(n):
            if i in skip:
                continue
            ts = first_ts + i * HOUR_MS
            w.writerow([ts, 100.0 + i, 101.0, 99.0, 100.0 + i + 0.5, 1.0])


class TestLoadDvol(unittest.TestCase):
    def test_returns_open_not_close(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 4)
            got = load_dvol(p, 1_000_000_000_000,
                            1_000_000_000_000 + 3 * DVOL_INTERVAL_MS)
            self.assertEqual([v for _, v in got], [50.0, 51.0, 52.0, 53.0])

    def test_gap_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 5, skip=(2,))
            with self.assertRaises(VrpGapError):
                load_dvol(p, 1_000_000_000_000,
                          1_000_000_000_000 + 4 * DVOL_INTERVAL_MS)

    def test_wrong_first_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 4)
            with self.assertRaises(VrpGapError):
                load_dvol(p, 1_000_000_000_000 - DVOL_INTERVAL_MS,
                          1_000_000_000_000 + 3 * DVOL_INTERVAL_MS)


class TestLoadSpotCloses(unittest.TestCase):
    def test_reads_close_column(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "spot.csv")
            _write_spot(p, 1_000_000_000_000, 3)
            got = load_spot_closes(p, 1_000_000_000_000,
                                   1_000_000_000_000 + 2 * HOUR_MS)
            self.assertEqual(got[1_000_000_000_000], 100.5)
            self.assertEqual(len(got), 3)

    def test_gap_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "spot.csv")
            _write_spot(p, 1_000_000_000_000, 5, skip=(2,))
            with self.assertRaises(VrpGapError):
                load_spot_closes(p, 1_000_000_000_000,
                                 1_000_000_000_000 + 4 * HOUR_MS)


import math  # noqa: E402

from moonface.research.vrp_measure import (  # noqa: E402
    ANNUALIZATION_HOURS,
    RV_HORIZON_HOURS,
    build_return_series,
    build_return_series_from_returns,
    rv_var,
    usable_mask,
)


class TestUsableMask(unittest.TestCase):
    def test_no_splices_all_usable(self):
        m = usable_mask(1_000_000_000_000, 5, frozenset())
        self.assertEqual(m, [True] * 5)

    def test_straddling_return_excluded(self):
        base = 1_000_000_000_000
        # bar at base+2h is spliced; returns stamped base+2h (uses base+1h,
        # base+2h) and base+3h (uses base+2h, base+3h) both straddle.
        spliced = frozenset({base + 2 * HOUR_MS})
        m = usable_mask(base, 5, spliced)
        self.assertEqual(m, [True, True, False, False, True])

    def test_interior_of_spliced_run_is_usable(self):
        base = 1_000_000_000_000
        spliced = frozenset({base + 2 * HOUR_MS, base + 3 * HOUR_MS})
        m = usable_mask(base, 5, spliced)
        # stamped base+3h uses two spliced bars -> Coinbase-to-Coinbase -> kept
        self.assertEqual(m, [True, True, False, True, False])


class TestRvVar(unittest.TestCase):
    def test_known_answer_constant_vol(self):
        """A path with a constant |log return| per hour must round-trip to
        the variance that generated it. This is the annualization guard."""
        base = 1_000_000_000_000
        step = 0.001  # |r| per hour
        n = RV_HORIZON_HOURS
        closes = {}
        price = 100.0
        closes[base - HOUR_MS] = price
        for i in range(n):
            price *= math.exp(step if i % 2 == 0 else -step)
            closes[base + i * HOUR_MS] = price
        series = build_return_series(closes, base, base + (n - 1) * HOUR_MS,
                                     spliced=frozenset())
        got = rv_var(series, base)
        self.assertAlmostEqual(got, step * step * ANNUALIZATION_HOURS, places=9)

    def test_excluded_returns_do_not_shrink_the_average(self):
        """Excluding a return divides by the true usable count, not by 720."""
        base = 1_000_000_000_000
        n = 4
        usable = [True, False, True, True]
        returns = [0.01, 99.0, 0.01, 0.01]  # 99.0 is the fake splice jump
        series = build_return_series_from_returns(returns, base, usable)
        got = rv_var(series, base, horizon=n)
        self.assertAlmostEqual(got, 0.0001 * ANNUALIZATION_HOURS, places=9)

    def test_window_is_exclusive_of_t_and_inclusive_of_t_plus_horizon(self):
        base = 1_000_000_000_000
        returns = [1.0, 2.0, 3.0, 4.0]
        series = build_return_series_from_returns(returns, base, [True] * 4)
        # horizon=2 from base must use returns stamped base and base+1h only
        got = rv_var(series, base, horizon=2)
        self.assertAlmostEqual(got, ((1.0 + 4.0) / 2) * ANNUALIZATION_HOURS, places=9)

    def test_reads_past_end_raises(self):
        base = 1_000_000_000_000
        series = build_return_series_from_returns([1.0, 2.0], base, [True] * 2)
        with self.assertRaises(VrpGapError):
            rv_var(series, base, horizon=5)

    def test_all_returns_excluded_raises(self):
        base = 1_000_000_000_000
        series = build_return_series_from_returns([1.0, 2.0], base, [False, False])
        with self.assertRaises(VrpGapError):
            rv_var(series, base, horizon=2)


from moonface.research.vrp_measure import (  # noqa: E402
    DISJOINT_STRIDE_MS,
    block_bootstrap_mean_ci,
    disjoint_spreads,
    iv_var,
    mean,
    percentile,
    plain_mean_ci,
    spread_series,
    year_buckets,
)


class TestIvVar(unittest.TestCase):
    def test_vol_points_to_annualized_variance(self):
        self.assertAlmostEqual(iv_var(50.0), 0.25, places=12)
        self.assertAlmostEqual(iv_var(100.0), 1.0, places=12)


class TestSpreadSeries(unittest.TestCase):
    def test_spread_is_iv_minus_rv(self):
        base = 1_000_000_000_000
        dvol = [(base, 50.0), (base + DVOL_INTERVAL_MS, 60.0)]
        # spread_series always uses the real 720h horizon, and the last DVOL
        # point is 12h in, so the series needs 720 + 12 returns.
        n = RV_HORIZON_HOURS + 12
        series = build_return_series_from_returns([0.0] * n, base, [True] * n)
        got = spread_series(dvol, series)
        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(got[0][1], 0.25, places=12)   # rv is 0
        self.assertAlmostEqual(got[1][1], 0.36, places=12)


class TestPercentile(unittest.TestCase):
    def test_linear_interpolation(self):
        v = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(percentile(v, 0.0), 1.0)
        self.assertAlmostEqual(percentile(v, 100.0), 4.0)
        self.assertAlmostEqual(percentile(v, 50.0), 2.5)

    def test_single_value(self):
        self.assertAlmostEqual(percentile([7.0], 97.5), 7.0)


class TestBlockBootstrap(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        v = [float(i % 7) for i in range(600)]
        a = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        b = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        v = [float(i % 7) for i in range(600)]
        a = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        b = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=2)
        self.assertNotEqual(a, b)

    def test_ci_brackets_the_mean(self):
        v = [float(i % 7) for i in range(600)]
        lo, hi = block_bootstrap_mean_ci(v, block_len=60, n_resamples=500, seed=1)
        self.assertLess(lo, mean(v))
        self.assertGreater(hi, mean(v))

    def test_series_shorter_than_block_raises(self):
        with self.assertRaises(ValueError):
            block_bootstrap_mean_ci([1.0] * 10, block_len=60, n_resamples=10, seed=1)


class TestDisjointSpreads(unittest.TestCase):
    def test_strides_by_30_days(self):
        base = 1_000_000_000_000
        spread = [(base + i * DVOL_INTERVAL_MS, float(i)) for i in range(200)]
        got = disjoint_spreads(spread, stride_ms=DISJOINT_STRIDE_MS)
        # 60 DVOL points per 30d stride: indices 0, 60, 120, 180
        self.assertEqual(got, [0.0, 60.0, 120.0, 180.0])


class TestPlainMeanCi(unittest.TestCase):
    def test_known_values(self):
        v = [1.0, 2.0, 3.0, 4.0, 5.0]
        lo, hi = plain_mean_ci(v)
        self.assertAlmostEqual((lo + hi) / 2, 3.0, places=12)
        self.assertLess(lo, 3.0)
        self.assertGreater(hi, 3.0)

    def test_too_few_raises(self):
        with self.assertRaises(ValueError):
            plain_mean_ci([1.0])


class TestYearBuckets(unittest.TestCase):
    def test_buckets_by_year_of_t(self):
        # 2021-12-31 12:00 UTC and 2022-01-01 00:00 UTC
        spread = [(1640953800000 - 1800000, 1.0), (1640995200000, 2.0)]
        got = year_buckets(spread)
        self.assertEqual(sorted(got), [2021, 2022])
        self.assertEqual(got[2021], [1.0])
        self.assertEqual(got[2022], [2.0])


import random as _random  # noqa: E402
import statistics as _stats  # noqa: E402

from moonface.research.vrp_measure import (  # noqa: E402
    N_NULL_SEEDS,
    T_DF,
    draw_gaussian,
    draw_student_t,
    null_distribution,
    null_mean_spread,
    sigma_path,
    synthetic_returns,
)


class TestSigmaPath(unittest.TestCase):
    def test_step_function_holds_dvol_across_its_bar(self):
        base = 1_000_000_000_000
        dvol = [(base, 50.0), (base + DVOL_INTERVAL_MS, 100.0)]
        sig = sigma_path(dvol, base, 13)
        expected_first = 0.5 / math.sqrt(ANNUALIZATION_HOURS)
        expected_last = 1.0 / math.sqrt(ANNUALIZATION_HOURS)
        for i in range(12):
            self.assertAlmostEqual(sig[i], expected_first, places=12)
        self.assertAlmostEqual(sig[12], expected_last, places=12)

    def test_before_first_bar_raises(self):
        base = 1_000_000_000_000
        with self.assertRaises(VrpGapError):
            sigma_path([(base, 50.0)], base - HOUR_MS, 2)


class TestDraws(unittest.TestCase):
    def test_gaussian_is_unit_variance(self):
        rng = _random.Random(7)
        xs = [draw_gaussian(rng) for _ in range(200_000)]
        self.assertAlmostEqual(_stats.pstdev(xs), 1.0, places=2)

    def test_student_t_rescaled_to_unit_variance(self):
        rng = _random.Random(7)
        xs = [draw_student_t(rng, df=T_DF) for _ in range(200_000)]
        self.assertAlmostEqual(_stats.pstdev(xs), 1.0, delta=0.05)

    def test_student_t_is_fatter_tailed_than_gaussian(self):
        rng = _random.Random(7)
        g = sorted(abs(draw_gaussian(rng)) for _ in range(100_000))
        t = sorted(abs(draw_student_t(rng, df=T_DF)) for _ in range(100_000))
        self.assertGreater(t[-100], g[-100])


class TestSyntheticReturns(unittest.TestCase):
    def test_scales_by_sigma(self):
        rng = _random.Random(3)
        sigmas = [0.01] * 50_000
        rs = synthetic_returns(sigmas, rng, draw_gaussian)
        self.assertEqual(len(rs), 50_000)
        self.assertAlmostEqual(_stats.pstdev(rs), 0.01, places=3)


class TestNull(unittest.TestCase):
    def _fixture(self, n_bars=200):
        base = 1_000_000_000_000
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(n_bars)]
        n_ret = (n_bars - 1) * 12 + RV_HORIZON_HOURS
        return base, dvol, n_ret

    def test_deterministic_for_a_seed(self):
        base, dvol, n_ret = self._fixture()
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        a = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        b = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        self.assertEqual(a, b)

    def test_null_spread_is_small_relative_to_iv(self):
        """Under the null there is no premium, so the mean spread must sit near
        zero -- far below iv_var itself. Catches a sign error or a
        squared/unsquared mixup."""
        base, dvol, n_ret = self._fixture()
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        got = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        self.assertLess(abs(got), 0.1 * iv_var(60.0))

    def test_distribution_length_and_determinism(self):
        base, dvol, n_ret = self._fixture(n_bars=70)
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        a = null_distribution(dvol, base, usable, sig, base_seed=11,
                              draw=draw_gaussian, n_seeds=5)
        b = null_distribution(dvol, base, usable, sig, base_seed=11,
                              draw=draw_gaussian, n_seeds=5)
        self.assertEqual(len(a), 5)
        self.assertEqual(a, b)

    def test_default_seed_count_is_frozen(self):
        self.assertEqual(N_NULL_SEEDS, 500)


from moonface.research.vrp_measure import (  # noqa: E402
    assemble_results,
    evaluate_threshold,
    render_results_md,
    tail_windows,
)


def _threshold_results(mean_spread, null_g_p975, null_t_p975, boot, disj,
                       buckets_positive):
    buckets = {}
    for i, positive in enumerate(buckets_positive):
        buckets[2021 + i] = {"mean": 1.0 if positive else -1.0, "n": 10}
    return {
        "mean_spread": mean_spread,
        "null_gaussian": {"p97_5": null_g_p975},
        "null_student_t": {"p97_5": null_t_p975},
        "bootstrap_ci": boot,
        "disjoint_ci": disj,
        "year_buckets": buckets,
    }


class TestEvaluateThreshold(unittest.TestCase):
    def test_all_three_clear(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertTrue(got["continue_recommended"])

    def test_fails_when_below_either_null(self):
        r = _threshold_results(0.05, 0.01, 0.09, (0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertFalse(got["null_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_fails_when_a_ci_straddles_zero(self):
        r = _threshold_results(0.05, 0.01, 0.02, (-0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertFalse(got["interval_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_fails_when_only_four_buckets_positive(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True, True, True, True, False, False])
        got = evaluate_threshold(r)
        self.assertFalse(got["stability_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_five_of_six_buckets_is_enough(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True, True, True, True, True, False])
        got = evaluate_threshold(r)
        self.assertTrue(got["stability_clears"])
        self.assertTrue(got["continue_recommended"])


class TestTailWindows(unittest.TestCase):
    def test_returns_k_highest_rv_windows(self):
        base = 1_000_000_000_000
        n_ret = 12 * 5 + RV_HORIZON_HOURS
        returns = [0.001] * n_ret
        # make the window starting at the 3rd DVOL bar the most volatile
        for i in range(24, 24 + RV_HORIZON_HOURS):
            returns[i] = 0.02
        series = build_return_series_from_returns(returns, base, [True] * n_ret)
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(5)]
        spread = spread_series(dvol, series)
        got = tail_windows(spread, series, k=2)
        self.assertEqual(len(got), 2)
        self.assertGreaterEqual(got[0]["rv_var"], got[1]["rv_var"])
        self.assertIn("date_utc", got[0])
        self.assertIn("spread", got[0])


class TestRender(unittest.TestCase):
    def test_renders_without_verdict_language(self):
        base = 1_000_000_000_000
        n_ret = 12 * 70 + RV_HORIZON_HOURS
        series = build_return_series_from_returns([0.001] * n_ret, base,
                                                 [True] * n_ret)
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(71)]
        results = assemble_results(dvol, series, n_null_seeds=3)
        md = render_results_md(results, {"commit": "abc123", "inputs_sha256": {}})
        self.assertIn("Q1", md)
        self.assertIn("Q4", md)
        lowered = md.lower()
        for banned in ("edge found", "kill", "buy", "sell", "recommend trading"):
            self.assertNotIn(banned, lowered)


import json as _json  # noqa: E402

from tools.lanes.vrp_measure import main as vrp_main  # noqa: E402
from tools.lanes.vrp_measure import sha256_of  # noqa: E402


class TestCliRunOnce(unittest.TestCase):
    def _inputs(self, d):
        """A small but structurally real fixture: 70 DVOL bars + enough spot."""
        base = 1_000_000_000_000
        n_bars = 70
        dvol_p = str(_Path(d) / "dvol.csv")
        with open(dvol_p, "w", newline="") as fh:
            w = _csv.writer(fh)
            for i in range(n_bars):
                w.writerow([base + i * DVOL_INTERVAL_MS, 60.0, 61.0, 59.0, 60.0])
        n_ret = (n_bars - 1) * 12 + RV_HORIZON_HOURS
        spot_p = str(_Path(d) / "spot.csv")
        price = 100.0
        with open(spot_p, "w", newline="") as fh:
            w = _csv.writer(fh)
            for i in range(n_ret + 1):
                ts = base - HOUR_MS + i * HOUR_MS
                price *= math.exp(0.001 if i % 2 == 0 else -0.001)
                w.writerow([ts, price, price, price, price, 1.0])
        return dvol_p, spot_p, base, n_bars

    def test_sha256_is_stable(self):
        with TemporaryDirectory() as d:
            p = _Path(d) / "x.txt"
            p.write_text("hello")
            self.assertEqual(sha256_of(str(p)), sha256_of(str(p)))
            self.assertEqual(len(sha256_of(str(p))), 64)

    def test_writes_outputs_then_refuses_second_run(self):
        with TemporaryDirectory() as d:
            dvol_p, spot_p, base, n_bars = self._inputs(d)
            outdir = str(_Path(d) / "out")
            argv = ["--dvol", dvol_p, "--spot", spot_p, "--outdir", outdir,
                    "--start-ms", str(base),
                    "--end-ms", str(base + (n_bars - 1) * DVOL_INTERVAL_MS),
                    "--null-seeds", "2"]
            self.assertEqual(vrp_main(argv), 0)
            self.assertTrue((_Path(outdir) / "RESULTS.md").exists())
            payload = _json.loads((_Path(outdir) / "results.json").read_text())
            self.assertIn("mean_spread", payload["results"])
            self.assertIn("dvol", payload["meta"]["inputs_sha256"])
            # second run must refuse
            self.assertEqual(vrp_main(argv), 1)

    def test_gap_in_input_is_a_hard_failure(self):
        with TemporaryDirectory() as d:
            dvol_p, spot_p, base, n_bars = self._inputs(d)
            rows = list(_csv.reader(open(spot_p)))
            del rows[50]
            with open(spot_p, "w", newline="") as fh:
                _csv.writer(fh).writerows(rows)
            argv = ["--dvol", dvol_p, "--spot", spot_p,
                    "--outdir", str(_Path(d) / "out2"),
                    "--start-ms", str(base),
                    "--end-ms", str(base + (n_bars - 1) * DVOL_INTERVAL_MS),
                    "--null-seeds", "2"]
            with self.assertRaises(VrpGapError):
                vrp_main(argv)
