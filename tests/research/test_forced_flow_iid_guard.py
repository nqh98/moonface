from dataclasses import replace
import math
import unittest
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.slow

try:
    from moonface.research.forced_flow import iid_guard
except ModuleNotFoundError:
    FROZEN = None
    Segment = None
    _causal_burst_z = None
    _finish_null = None
    _percentile = None
    build_pipeline = None
    iid_guard = None
    run_null_battery = None
else:
    FROZEN = iid_guard.FROZEN
    Segment = getattr(iid_guard, "Segment", None)
    _causal_burst_z = iid_guard._causal_burst_z
    _finish_null = iid_guard._finish_null
    _percentile = iid_guard._percentile
    build_pipeline = iid_guard.build_pipeline
    run_null_battery = iid_guard.run_null_battery


def _directionless_synthetic_inputs() -> tuple[list[float], list[int], list[float]]:
    """A non-zero, mean-zero return path independent of liquidation features."""
    bars = 2_100
    closes = [100.0]
    for bar in range(1, bars):
        log_return = (((bar * 17) % 31) - 15) * 0.0001
        closes.append(closes[-1] * math.exp(log_return))

    counts = [bar % 2 for bar in range(bars)]
    imbalances = [0.0] * bars
    for episode_number, bar in enumerate(range(250, bars - 24, 7)):
        counts[bar] = (1_000_000, 3_000_000, 9_000_000)[episode_number % 3]
        imbalances[bar] = 1.0 if episode_number % 2 == 0 else -1.0
    return closes, counts, imbalances


class TestForcedFlowIidGuard(unittest.TestCase):
    def test_p975_uses_higher_empirical_quantile(self):
        self.assertEqual(_percentile([0.0, 10.0, 20.0, 30.0], 0.975), 30.0)

    def test_iid_guard_fails_on_directionless_synthetic_data(self):
        self.assertIsNotNone(FROZEN)
        self.assertIsNotNone(run_null_battery)
        self.assertEqual(FROZEN.bar_hours, 1)
        self.assertEqual(FROZEN.z_window_bars, 720)
        self.assertEqual(FROZEN.min_history_bars, 240)
        self.assertEqual(FROZEN.entry_threshold, 2.0)
        self.assertEqual(FROZEN.rearm_bars, 6)
        self.assertEqual(FROZEN.horizon_bars, 24)
        self.assertEqual(FROZEN.power_floor, 30)
        self.assertEqual(FROZEN.null_draws, 1_000)
        self.assertEqual(FROZEN.seed, 1337)

        closes, counts, imbalances = _directionless_synthetic_inputs()
        result = run_null_battery(closes, counts, imbalances)

        self.assertIsNotNone(result.pipeline.spread)
        self.assertEqual(len(result.label_shuffle.null_spreads), FROZEN.null_draws)
        self.assertEqual(len(result.circular_shift.null_spreads), FROZEN.null_draws)
        self.assertEqual(len(result.iid_return.null_spreads), FROZEN.null_draws)
        self.assertEqual(result.label_shuffle.discarded_draws, 0)
        self.assertEqual(result.circular_shift.discarded_draws, 0)
        self.assertEqual(result.iid_return.discarded_draws, 0)
        self.assertFalse(result.iid_return.passed)

    def test_causal_z_uses_sample_variance(self):
        self.assertIsNotNone(_causal_burst_z)
        counts = [0] * 239 + [3, 1]

        score = _causal_burst_z(counts)[240]

        history = [math.log1p(count) for count in counts[:240]]
        mean = sum(history) / len(history)
        sample_variance = sum((value - mean) ** 2 for value in history) / (len(history) - 1)
        self.assertAlmostEqual(score, (math.log(2) - mean) / math.sqrt(sample_variance))

    def test_undefined_z_resets_rearm_streak(self):
        self.assertIsNotNone(build_pipeline)
        z_scores = [0.0] * FROZEN.rearm_bars + [None, 0.0, FROZEN.entry_threshold]
        closes = [100.0] * (len(z_scores) + FROZEN.horizon_bars)
        counts = [0] * len(closes)
        imbalances = [0.0] * len(closes)
        imbalances[len(z_scores) - 1] = 1.0

        with patch.object(iid_guard, "_causal_burst_z", return_value=z_scores):
            result = build_pipeline(closes, counts, imbalances)

        self.assertEqual(result.episodes, ())

    def test_segments_do_not_concatenate_across_a_gap(self):
        self.assertIsNotNone(build_pipeline)
        segment_length = 1_500
        counts = [index % 2 for index in range(segment_length * 2)]
        for bar_index in (246, 720, segment_length + 246, segment_length + 720):
            counts[bar_index] = 1_000_000
        closes = [100.0 * math.exp(index * 0.0001) for index in range(len(counts))]
        imbalances = [1.0 if count == 1_000_000 else 0.0 for count in counts]
        segments = (
            Segment(0, segment_length, starts_after_gap=False),
            Segment(segment_length, segment_length * 2, starts_after_gap=True),
        )

        result = build_pipeline(closes, counts, imbalances, segments=segments)

        self.assertEqual(
            {episode.bar_index for episode in result.episodes},
            {246, 720, segment_length + 720},
        )

    def test_horizon_endpoint_on_final_bar_is_eligible(self):
        self.assertIsNotNone(build_pipeline)
        length = 1_500
        entry = length - FROZEN.horizon_bars - 1
        counts = [index % 2 for index in range(length)]
        counts[entry] = 1_000_000
        closes = [100.0 * math.exp(index * 0.0001) for index in range(length)]
        imbalances = [1.0 if index == entry else 0.0 for index in range(length)]

        result = build_pipeline(closes, counts, imbalances)

        self.assertIn(entry, {episode.bar_index for episode in result.episodes})

    def test_null_result_keeps_powered_draws_and_counts_discards(self):
        self.assertIsNotNone(_finish_null)
        with patch.object(iid_guard, "FROZEN", replace(FROZEN, null_draws=4)):
            result = _finish_null(0.5, (0.1, 0.2), discarded_draws=2)

        self.assertEqual(result.null_spreads, (0.1, 0.2))
        self.assertEqual(result.discarded_draws, 2)
        self.assertEqual(result.threshold_p975, 0.2)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
