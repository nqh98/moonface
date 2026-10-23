import tempfile
import unittest
from pathlib import Path

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.sse.axes import AxisMatrix, build_axes
from moonface.research.sse.clusters import UNLABELED, assign_clusters, fit_kmeans
from moonface.research.sse.episodes import assign_eras, entry_episodes
from moonface.research.sse.gate import gate0_result, spread_stat
from moonface.research.sse.report import render_gate0_report, write_gate0_artifacts
from moonface.research.sse.trajectory import summarize_trajectories
from moonface.research.sse.universe import monthly_membership
from moonface.research.universe_data import DailyRow

DAY = 86_400_000
H4 = 14_400_000


def _bundle(n: int, *, drift: float = 0.0, start: float = 100.0, ts0: int = 0) -> DataBundle:
    closes = []
    price = start
    for i in range(n):
        price *= 1.0 + drift + (0.002 if i % 2 else -0.001)
        closes.append(price)
    candles = [
        Candle(ts0 + i * H4, c, c * 1.01, c * 0.99, c, 1000.0 + i)
        for i, c in enumerate(closes)
    ]
    return DataBundle(candles=candles)


class TestUniverse(unittest.TestCase):
    def test_monthly_membership_rebuilds_on_month_boundary(self):
        jan = 1_735_689_600_000
        daily_start = jan - 100 * DAY
        daily = {
            "AUSDT": [DailyRow(daily_start + i * DAY, 100.0, 5_000.0) for i in range(120)],
            "BUSDT": [DailyRow(daily_start + i * DAY, 100.0, 4_000.0) for i in range(120)],
            "CUSDT": [DailyRow(daily_start + i * DAY, 100.0, 3_000.0) for i in range(120)],
        }
        feb = 1_738_368_000_000
        sched = monthly_membership(
            daily, [jan, jan + H4, feb], top_n=2, min_history_days=30, vol_days=30
        )
        self.assertEqual(sched.members[0], {"AUSDT", "BUSDT"})
        self.assertEqual(sched.members[2], {"AUSDT", "BUSDT"})


class TestAxesAndTrajectory(unittest.TestCase):
    def test_axes_require_min_active(self):
        start = 40 * DAY
        pool = {
            f"S{i:02d}USDT": _bundle(40, drift=0.001 * (i % 3 - 1), ts0=start)
            for i in range(6)
        }
        sched = monthly_membership(
            {sym: [DailyRow(start + j * DAY, 100.0, 1_000.0 + i) for j in range(120)]
             for i, sym in enumerate(pool)},
            [start + i * H4 for i in range(40)],
            top_n=6,
            min_history_days=0,
            vol_days=5,
        )
        axes = build_axes(pool, sched, ma_period=5, ret_bars=2, z_window=8, min_frac=0.75, min_active=4)
        self.assertEqual(len(axes.breadth_z), 40)
        self.assertIsNotNone(axes.raw_breadth[-1])
        self.assertIsNotNone(axes.raw_disp[-1])

    def test_trajectory_standardizes_varying_state_path(self):
        axes = AxisMatrix(
            timestamps=[i * H4 for i in range(16)],
            raw_breadth=[None] * 16,
            raw_disp=[None] * 16,
            breadth_z=[None, None, 0.1, 0.4, 0.2, 0.6, 0.1, -0.2, 0.3, 0.7, 0.5, 0.0, -0.3, 0.2, 0.4, 0.8],
            disp_z=[None, None, -0.2, 0.0, 0.3, 0.1, 0.5, 0.2, -0.1, 0.4, 0.6, 0.3, 0.0, -0.2, 0.1, 0.5],
            active_counts=[6] * 16,
        )
        traj = summarize_trajectories(axes, lookback=4, z_window=6, min_frac=0.75)
        self.assertEqual(len(traj.rows), 16)
        self.assertIn("breadth_mean", traj.rows[-1])
        self.assertIsNotNone(traj.rows[-1]["breadth_mean"])


class TestClustersAndEpisodes(unittest.TestCase):
    def test_kmeans_assigns_separated_rows(self):
        rows = (
            [{"x": -2.0, "y": -2.0}, {"x": -1.8, "y": -2.1}, {"x": -2.2, "y": -1.7}]
            + [{"x": 2.0, "y": 2.0}, {"x": 2.2, "y": 1.8}, {"x": 1.7, "y": 2.1}]
            + [{"x": None, "y": 1.0}]
        )
        model = fit_kmeans(rows, feature_names=("x", "y"), fit_mask=[True] * len(rows), k=2, seed=7)
        labels = assign_clusters(rows, model)
        self.assertEqual(labels[-1], UNLABELED)
        self.assertEqual(len({labels[0], labels[1], labels[2]}), 1)
        self.assertEqual(len({labels[3], labels[4], labels[5]}), 1)
        self.assertNotEqual(labels[0], labels[3])

    def test_entry_episodes_only_on_cluster_transitions(self):
        candles = [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(10)]
        labels = [UNLABELED, 0, 0, 1, 1, 1, 0, 0, UNLABELED, 2]
        episodes = entry_episodes(labels, candles, horizon=2)
        self.assertEqual([row["cluster"] for row in episodes], [0, 1, 0])
        eras = assign_eras([row["ts_ms"] for row in episodes], [(0, 4 * H4), (4 * H4, 8 * H4)])
        self.assertEqual(eras, [1, 1, 2])


class TestGateAndReport(unittest.TestCase):
    def test_gate0_passes_when_track_n_separates_and_control_does_not(self):
        labels: list[int] = []
        closes: list[float] = []
        price = 100.0
        for block in range(60):
            label = block % 2
            for step in range(8):
                labels.append(label)
                if step < 4:
                    price += 2.0 if label == 1 else -2.0
                closes.append(price)
        candles = [Candle(i * H4, c, c + 1.0, c - 1.0, c, 1000.0) for i, c in enumerate(closes)]
        episodes_n = entry_episodes(labels, candles, horizon=4)
        era_cut1 = candles[len(candles) // 3].timestamp_ms
        era_cut2 = candles[(2 * len(candles)) // 3].timestamp_ms
        for row in episodes_n:
            row["era"] = 1 if row["ts_ms"] < era_cut1 else 2 if row["ts_ms"] < era_cut2 else 3
        episodes_l = [{**row, "fwd_r": 0.0} for row in episodes_n]
        result = gate0_result(
            track_n_episodes=episodes_n,
            track_l_episodes=episodes_l,
            labels=labels,
            candles=candles,
            horizon=4,
            draws=50,
            seed=3,
            power_floor=8,
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertGreater(spread_stat(episodes_n, power_floor=8), 0.0)
        text = render_gate0_report(result)
        self.assertIn("verdict: PASS", text)
        with tempfile.TemporaryDirectory() as tmp:
            write_gate0_artifacts(Path(tmp), result)
            self.assertTrue((Path(tmp) / "gate0_verdict.json").exists())
            self.assertTrue((Path(tmp) / "gate0_report.md").exists())


if __name__ == "__main__":
    unittest.main()
