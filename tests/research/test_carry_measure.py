"""Tests for the carry_measure measurement lane.

See experiments/carry_measure/SPEC.md. This lane is descriptive accounting:
no forecasting, no optimization. Fixtures are synthetic unless explicitly
labeled as the hand-verified real month.
"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.research.carry_measure import (
    DAY_MS,
    FUNDING_INTERVAL_MS,
    HOUR_MS,
    GapError,
    ascii_histogram,
    assemble_results,
    basis_haircuts,
    basis_series,
    block_bootstrap_dd,
    drawdown_stats,
    load_bars_1h,
    load_funding,
    max_runup,
    monthly_rate_sums,
    monthly_sums,
    negative_episodes,
    percentile,
    price_at,
    quarterly_sums,
    render_results_md,
    run_ledger,
    runup_windows,
    yearly_rate_stats,
)

START = 1_577_836_800_000  # 2020-01-01 00:00 UTC


def write_funding_csv(path: Path, rates: list[float], start_ms: int = START,
                      jitter_ms: int = 5) -> None:
    """Funding CSV with the real files' millisecond timestamp jitter."""
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        for i, rate in enumerate(rates):
            writer.writerow([start_ms + i * FUNDING_INTERVAL_MS + jitter_ms, rate])


def write_bars_csv(path: Path, n_bars: int, start_ms: int = START,
                   price: float = 100.0, prices: list[float] | None = None) -> None:
    """Contiguous 1h kline CSV; constant price unless `prices` given per bar."""
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        for i in range(n_bars):
            p = prices[i] if prices is not None else price
            writer.writerow([start_ms + i * HOUR_MS, p, p, p, p, 1.0])


class TestLoaders(unittest.TestCase):
    def test_load_funding_normalizes_jitter_and_validates(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "funding.csv"
            write_funding_csv(path, [0.0001, -0.0002, 0.0003])
            end = START + 2 * FUNDING_INTERVAL_MS
            points = load_funding(str(path), START, end)
            self.assertEqual([ts for ts, _ in points],
                             [START, START + FUNDING_INTERVAL_MS, end])
            self.assertEqual([r for _, r in points], [0.0001, -0.0002, 0.0003])

    def test_load_funding_gap_raises(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "funding.csv"
            with open(path, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([START, 0.0001])
                # skip one interval
                writer.writerow([START + 2 * FUNDING_INTERVAL_MS, 0.0001])
            with self.assertRaises(GapError):
                load_funding(str(path), START, START + 2 * FUNDING_INTERVAL_MS)

    def test_load_funding_missing_endpoint_raises(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "funding.csv"
            write_funding_csv(path, [0.0001, 0.0001])
            with self.assertRaises(GapError):  # asks for 3 points, file has 2
                load_funding(str(path), START, START + 2 * FUNDING_INTERVAL_MS)

    def test_load_bars_and_price_at(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            write_bars_csv(path, 25, prices=[100.0 + i for i in range(25)])
            bars = load_bars_1h(str(path), START, START + 24 * HOUR_MS)
            self.assertEqual(len(bars), 25)
            self.assertEqual(price_at(bars, START), 100.0)
            self.assertEqual(price_at(bars, START + 8 * HOUR_MS), 108.0)
            with self.assertRaises(GapError):
                price_at(bars, START + 25 * HOUR_MS)

    def test_load_bars_gap_raises(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            with open(path, "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([START, 100, 100, 100, 100, 1.0])
                writer.writerow([START + 2 * HOUR_MS, 100, 100, 100, 100, 1.0])
            with self.assertRaises(GapError):
                load_bars_1h(str(path), START, START + 2 * HOUR_MS)


def make_funding(rates: list[float], start_ms: int = START) -> list[tuple[int, float]]:
    return [(start_ms + i * FUNDING_INTERVAL_MS, r) for i, r in enumerate(rates)]


def make_bars(n_hours: int, start_ms: int = START, price: float = 100.0,
              prices: list[float] | None = None) -> dict[int, tuple[float, float]]:
    out = {}
    for i in range(n_hours + 1):
        p = prices[i] if prices is not None else price
        out[start_ms + i * HOUR_MS] = (p, p)
    return out


class TestLedgerR0(unittest.TestCase):
    def test_sign_convention_short_receives_positive_funding(self):
        funding = make_funding([0.0001])
        bars = make_bars(0)
        rows = run_ledger(funding, bars, "R0", 0.0)
        self.assertAlmostEqual(rows[0].funding_usd, 0.0001, places=12)

    def test_negative_rate_costs_the_short(self):
        rows = run_ledger(make_funding([-0.0002]), make_bars(0), "R0", 0.0)
        self.assertAlmostEqual(rows[0].funding_usd, -0.0002, places=12)

    def test_zero_rates_zero_gross(self):
        rows = run_ledger(make_funding([0.0] * 10), make_bars(80), "R0", 0.0)
        self.assertEqual(rows[-1].cum_net_usd, 0.0)

    def test_all_positive_flat_price_gross_is_sum_of_rates(self):
        rates = [0.0001, 0.0003, 0.00005]
        rows = run_ledger(make_funding(rates), make_bars(16), "R0", 0.0)
        self.assertAlmostEqual(rows[-1].cum_net_usd, sum(rates), places=12)

    def test_r0_quantity_fixed_while_price_moves(self):
        # price doubles: q stays n0/p0, funding accrues on the doubled notional
        prices = [100.0] * 8 + [200.0] * 9
        funding = make_funding([0.0001, 0.0001])
        rows = run_ledger(funding, make_bars(16, prices=prices), "R0", 0.0)
        self.assertAlmostEqual(rows[0].q_btc, 0.01, places=12)
        self.assertAlmostEqual(rows[1].q_btc, 0.01, places=12)
        self.assertAlmostEqual(rows[1].funding_usd, 0.0001 * 0.01 * 200.0, places=12)

    def test_entry_and_exit_costs_charged(self):
        # 10 bps quoted: entry = 10bps of n0, exit = 10bps of q*P_exit
        rows = run_ledger(make_funding([0.0, 0.0]), make_bars(8), "R0", 10.0)
        self.assertAlmostEqual(rows[0].cost_usd, 0.001, places=12)
        self.assertAlmostEqual(rows[-1].cost_usd, 0.001, places=12)
        self.assertAlmostEqual(rows[-1].cum_net_usd, -0.002, places=12)


class TestConventions(unittest.TestCase):
    def _month_of_funding(self, n_intervals: int) -> list[tuple[int, float]]:
        return make_funding([0.0001] * n_intervals)

    def test_flat_prices_all_conventions_identical(self):
        # SPEC §7: flat prices -> R0 == R1a == R1b (no drift -> no resize cost)
        funding = self._month_of_funding(200)  # crosses a month boundary
        bars = make_bars(200 * 8)
        curves = [run_ledger(funding, bars, conv, 10.0)[-1].cum_net_usd
                  for conv in ("R0", "R1a", "R1b")]
        self.assertAlmostEqual(curves[0], curves[1], places=12)
        self.assertAlmostEqual(curves[0], curves[2], places=12)

    def test_r1b_resizes_only_beyond_threshold(self):
        # +5% price move: no resize; +15%: resize back to n0
        prices_5 = [100.0] * 8 + [105.0] * 9
        prices_15 = [100.0] * 8 + [115.0] * 9
        funding = make_funding([0.0, 0.0])
        rows_5 = run_ledger(funding, make_bars(16, prices=prices_5), "R1b", 0.0)
        rows_15 = run_ledger(funding, make_bars(16, prices=prices_15), "R1b", 0.0)
        self.assertEqual(rows_5[1].q_btc, rows_5[0].q_btc)
        self.assertAlmostEqual(rows_15[1].q_btc, 1.0 / 115.0, places=12)

    def test_r1a_resizes_at_month_boundary_and_pays_cost(self):
        # 100 intervals from Jan 1: crosses into February; price drifted, so
        # the February resize trades a non-zero notional and costs > 0.
        n = 100
        prices = [100.0 + 0.05 * i for i in range(n * 8 + 1)]
        funding = make_funding([0.0] * n)
        rows = run_ledger(funding, make_bars(n * 8, prices=prices), "R1a", 10.0)
        resize_costs = [r.cost_usd for r in rows[1:-1] if r.cost_usd > 0]
        self.assertEqual(len(resize_costs), 1)  # exactly one month boundary inside

    def test_doubling_costs_never_increases_net(self):
        prices = [100.0 * (1.0 + 0.001 * i) for i in range(300 * 8 + 1)]
        funding = make_funding([0.0001] * 300)
        bars = make_bars(300 * 8, prices=prices)
        for conv in ("R0", "R1a", "R1b"):
            net_10 = run_ledger(funding, bars, conv, 10.0)[-1].cum_net_usd
            net_20 = run_ledger(funding, bars, conv, 20.0)[-1].cum_net_usd
            self.assertLess(net_20, net_10)

    def test_unknown_convention_rejected(self):
        with self.assertRaises(ValueError):
            run_ledger(make_funding([0.0]), make_bars(0), "R2", 0.0)


class TestAggregation(unittest.TestCase):
    def test_episode_detector_finds_exact_runs(self):
        rates = [0.0001, -0.0001, -0.0003, 0.0002, -0.0005]
        eps = negative_episodes(make_funding(rates))
        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0].n_intervals, 2)
        self.assertAlmostEqual(eps[0].depth_rate_sum, -0.0004, places=12)
        self.assertEqual(eps[0].start_ts, START + FUNDING_INTERVAL_MS)
        self.assertEqual(eps[1].n_intervals, 1)
        self.assertAlmostEqual(eps[1].depth_rate_sum, -0.0005, places=12)

    def test_no_negative_rates_no_episodes(self):
        self.assertEqual(negative_episodes(make_funding([0.0001] * 5)), [])

    def test_trailing_negative_run_is_closed(self):
        eps = negative_episodes(make_funding([0.0001, -0.0001, -0.0002]))
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0].n_intervals, 2)

    def test_percentile_linear_interpolation(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(percentile(vals, 50), 3.0)
        self.assertAlmostEqual(percentile(vals, 95), 4.8)
        self.assertAlmostEqual(percentile(vals, 0), 1.0)
        self.assertAlmostEqual(percentile(vals, 100), 5.0)

    def test_monthly_rate_sums_split_on_utc_month(self):
        # 100 intervals from Jan 1 2020 -> Jan has 93 (31d*3), Feb has 7
        sums = monthly_rate_sums(make_funding([0.0001] * 100))
        self.assertEqual(sums[0][:2], (2020, 1))
        self.assertAlmostEqual(sums[0][2], 93 * 0.0001, places=12)
        self.assertEqual(sums[1][:2], (2020, 2))
        self.assertAlmostEqual(sums[1][2], 7 * 0.0001, places=12)

    def test_yearly_rate_stats_annualization(self):
        stats = yearly_rate_stats(make_funding([0.0001] * 100))
        self.assertEqual(stats[0]["year"], 2020)
        self.assertEqual(stats[0]["n"], 100)
        self.assertAlmostEqual(stats[0]["ann_pct"], 0.0001 * 1095 * 100, places=9)

    def test_monthly_and_quarterly_sums_from_ledger(self):
        rows = run_ledger(make_funding([0.0001] * 100), make_bars(800), "R0", 0.0)
        months = monthly_sums(rows)
        self.assertEqual(len(months), 2)
        self.assertAlmostEqual(months[0][2], 93 * 0.0001, places=12)
        quarters = quarterly_sums(rows)
        self.assertEqual(len(quarters), 1)  # Jan+Feb are both Q1
        self.assertAlmostEqual(quarters[0][3], sum(r.net_usd for r in rows), places=12)


class TestRiskCurves(unittest.TestCase):
    def test_drawdown_stats_constructed_curve(self):
        ts = [START + i * HOUR_MS for i in range(6)]
        cum = [1.0, 2.0, 1.5, 0.5, 1.0, 3.0]
        stats = drawdown_stats(ts, cum)
        self.assertAlmostEqual(stats["max_dd"], 1.5)
        self.assertEqual(stats["peak_ts"], ts[1])
        self.assertEqual(stats["trough_ts"], ts[3])
        # underwater from the high at ts[1] until the new high at ts[5]
        self.assertAlmostEqual(stats["longest_uw_days"], 4 * HOUR_MS / DAY_MS)

    def test_drawdown_baseline_zero_catches_initial_costs(self):
        ts = [START, START + HOUR_MS]
        stats = drawdown_stats(ts, [-0.002, -0.001])
        self.assertAlmostEqual(stats["max_dd"], 0.002)

    def test_bootstrap_deterministic_and_ordered(self):
        rng_net = [0.0001 if i % 7 else -0.0005 for i in range(400)]
        a = block_bootstrap_dd(rng_net, block_len=30, n_resamples=200, seed=1)
        b = block_bootstrap_dd(rng_net, block_len=30, n_resamples=200, seed=1)
        self.assertEqual(a, b)
        self.assertLessEqual(a[0], a[1])
        self.assertGreaterEqual(a[0], 0.0)

    def test_max_runup(self):
        marks = [(START + i * FUNDING_INTERVAL_MS, p)
                 for i, p in enumerate([100.0, 90.0, 95.0, 120.0, 110.0])]
        runup, t0, t1 = max_runup(marks)
        self.assertAlmostEqual(runup, 120.0 / 90.0 - 1.0, places=12)
        self.assertEqual(t0, marks[1][0])
        self.assertEqual(t1, marks[3][0])

    def test_runup_windows_respect_window(self):
        # +50% happens over 20 intervals (~6.7 days at 8h): inside the 7d
        # window only partially, fully inside 30d
        prices = [100.0 + 2.5 * i for i in range(21)] + [152.5] * 10
        marks = [(START + i * FUNDING_INTERVAL_MS, p) for i, p in enumerate(prices)]
        out = runup_windows(marks, window_days=(7, 30))
        self.assertLess(out[7], out[30])
        self.assertAlmostEqual(out[30], 1.525 - 1.0, places=6)


class TestBasis(unittest.TestCase):
    def test_basis_series_values_and_gap(self):
        perp = make_bars(3, prices=[101.0, 101.0, 99.0, 100.0])
        spot = make_bars(3, prices=[100.0, 100.0, 100.0, 100.0])
        series = basis_series(perp, spot, START, START + 3 * HOUR_MS)
        self.assertEqual(len(series), 4)
        self.assertAlmostEqual(series[0][1], 0.01, places=12)
        self.assertAlmostEqual(series[2][1], -0.01, places=12)
        del spot[START + 2 * HOUR_MS]
        with self.assertRaises(GapError):
            basis_series(perp, spot, START, START + 3 * HOUR_MS)

    def test_haircuts_signs(self):
        # persistent backwardation: entering costs, exiting is free
        haircuts = basis_haircuts([-0.001, -0.002, -0.0005])
        self.assertGreater(haircuts["entry_median_bps"], 0.0)
        self.assertEqual(haircuts["exit_median_bps"], 0.0)
        self.assertGreaterEqual(haircuts["entry_p5_adverse_bps"],
                                haircuts["entry_median_bps"])


def synthetic_inputs(n_intervals: int = 380):
    """Roughly four months of synthetic data: mildly positive funding with a
    negative patch, gently rising price. Exercises every Q-computation."""
    rates = [0.0001] * n_intervals
    for i in range(40, 52):
        rates[i] = -0.0003
    funding = make_funding(rates)
    n_hours = n_intervals * 8
    prices = [100.0 * (1.0 + 0.0002 * i) for i in range(n_hours + 1)]
    perp = make_bars(n_hours, prices=prices)
    spot = make_bars(n_hours, prices=[p * 0.9995 for p in prices])
    return funding, perp, spot


class TestAssembleAndRender(unittest.TestCase):
    def test_assemble_results_structure(self):
        funding, perp, spot = synthetic_inputs()
        results = assemble_results(funding, perp, spot)
        for key in ("window", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "runups"):
            self.assertIn(key, results)
        self.assertEqual(len(results["q2"]), 9)  # 3 conventions x 3 cost levels
        self.assertEqual(results["q3"]["count"], 1)
        self.assertEqual(results["q3"]["longest_run_intervals"], 12)
        for conv in ("R0", "R1a", "R1b"):
            self.assertIn(conv, results["q4"])
            self.assertIn(conv, results["q7"])

    def test_assemble_handles_zero_episodes(self):
        funding, perp, spot = synthetic_inputs()
        funding = [(ts, abs(r)) for ts, r in funding]
        results = assemble_results(funding, perp, spot)
        self.assertEqual(results["q3"]["count"], 0)
        self.assertEqual(results["q3"]["deepest"], [])

    def test_render_ends_with_mandated_line(self):
        funding, perp, spot = synthetic_inputs()
        results = assemble_results(funding, perp, spot)
        meta = {"commit": "deadbeef", "seed": 20260716,
                "inputs_sha256": {"funding": {"path": "f.csv", "sha256": "aa"},
                                  "perp": {"path": "p.csv", "sha256": "bb"},
                                  "spot": {"path": "s.csv", "sha256": "cc"}}}
        text = render_results_md(results, meta)
        self.assertTrue(text.rstrip().endswith(
            "This is input to a personal investment decision, not a research verdict."))
        self.assertIn("## Risks", text)
        self.assertIn("deadbeef", text)
        lowered = text.lower()
        for banned in ("recommend", "should invest", "edge found", "kill"):
            self.assertNotIn(banned, lowered)

    def test_ascii_histogram_deterministic(self):
        text = ascii_histogram([1.0, 1.0, 2.0, 5.0], n_bins=4, width=10)
        lines = text.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].endswith(" 2"))   # two values in the first bin
        self.assertTrue(lines[-1].endswith(" 1"))  # one value in the last bin


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "carry_measure"


class TestFixtureMonth(unittest.TestCase):
    """Hand-verified real month 2021-05 (SPEC §7 criterion: earliest
    2021-2022 month with >= 5 negative 8h intervals -- May 2021 has 7,
    the earliest eligible month among the 2021-2022 counts).

    Expected values derived by an independent script (plan Task 8 Step 3)
    and spot-checked by hand (q = 1/57688.29, the first bar's open):
        1619827200000  rate=0.00011209  price=57688.29  cashflow=0.00011209000000000002
        1619856000000  rate=0.0001      price=57771.38  cashflow=0.00010014403269710369
        1619884800000  rate=0.00032496  price=57395.33  cashflow=0.0003233097468619715
    Hand check: cashflow = rate * (price / first_price). Row 2:
    57771.38 / 57688.29 = 1.0014403..., times 0.0001 = 0.00010014403...
    matches. Row 3: 57395.33 / 57688.29 = 0.9949218..., times 0.00032496 =
    0.00032330975... matches. A negative-rate spot check at ts=1621440000000
    (rate=-0.00089697, price=37304.85) gives cashflow=-0.00058003680...,
    confirming the short pays when the rate is negative.
    """

    FIX_START = 1619827200000
    FIX_END = 1622476800000
    EXPECTED_GROSS = 0.02123814914258509
    EXPECTED_NET10 = 0.01959773962446625

    def _load(self):
        funding = load_funding(str(FIXTURE_DIR / "fixture_funding.csv"),
                               self.FIX_START, self.FIX_END)
        bars = load_bars_1h(str(FIXTURE_DIR / "fixture_bars.csv"),
                            self.FIX_START, self.FIX_END)
        return funding, bars

    def test_month_meets_selection_criterion(self):
        funding, _ = self._load()
        self.assertGreaterEqual(sum(1 for _, r in funding if r < 0), 5)

    def test_gross_matches_hand_computation(self):
        funding, bars = self._load()
        rows = run_ledger(funding, bars, "R0", 0.0)
        self.assertAlmostEqual(rows[-1].cum_net_usd, self.EXPECTED_GROSS, places=10)

    def test_net_10bps_matches_hand_computation(self):
        funding, bars = self._load()
        rows = run_ledger(funding, bars, "R0", 10.0)
        self.assertAlmostEqual(rows[-1].cum_net_usd, self.EXPECTED_NET10, places=10)


class TestCli(unittest.TestCase):
    def _write_inputs(self, tmp: Path, n_intervals: int = 380):
        rates = [0.0001] * n_intervals
        for i in range(40, 52):
            rates[i] = -0.0003
        write_funding_csv(tmp / "funding.csv", rates)
        n_hours = n_intervals * 8
        prices = [100.0 * (1.0 + 0.0002 * i) for i in range(n_hours + 1)]
        write_bars_csv(tmp / "perp.csv", n_hours + 1, prices=prices)
        write_bars_csv(tmp / "spot.csv", n_hours + 1,
                       prices=[p * 0.9995 for p in prices])
        end = START + (n_intervals - 1) * FUNDING_INTERVAL_MS
        return ["--funding", str(tmp / "funding.csv"),
                "--perp", str(tmp / "perp.csv"),
                "--spot", str(tmp / "spot.csv"),
                "--outdir", str(tmp / "out"),
                "--start-ms", str(START), "--end-ms", str(end)]

    def test_cli_writes_once_then_refuses(self):
        from tools.lanes.carry_measure import main
        import json
        with TemporaryDirectory() as tmp:
            argv = self._write_inputs(Path(tmp))
            self.assertEqual(main(argv), 0)
            results_md = Path(tmp) / "out" / "RESULTS.md"
            self.assertTrue(results_md.exists())
            payload = json.loads((Path(tmp) / "out" / "results.json").read_text())
            self.assertIn("meta", payload)
            self.assertEqual(len(payload["meta"]["inputs_sha256"]), 3)
            for info in payload["meta"]["inputs_sha256"].values():
                self.assertEqual(len(info["sha256"]), 64)
            text = results_md.read_text()
            self.assertTrue(text.rstrip().endswith(
                "This is input to a personal investment decision, "
                "not a research verdict."))
            # second invocation must refuse
            self.assertEqual(main(argv), 1)


if __name__ == "__main__":
    unittest.main()
