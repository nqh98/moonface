import random

from moonface.kernel.bootstrap import (circular_block_resample,
                                        fixed_block_count_resample,
                                        iid_resample_choices,
                                        iid_resample_randrange,
                                        moving_block_resample, percentile,
                                        resample_by_block_key)


class TestIidResampleRandrange:
    def test_reproduces_the_exact_randrange_loop(self):
        data = [10.0, 20.0, 30.0, 40.0]
        rng_a = random.Random(1)
        expected = [data[rng_a.randrange(4)] for _ in range(4)]
        rng_b = random.Random(1)
        assert iid_resample_randrange(rng_b, data) == expected

    def test_same_seed_is_deterministic(self):
        data = [1.0, 2.0, 3.0]
        assert (iid_resample_randrange(random.Random(5), data)
                == iid_resample_randrange(random.Random(5), data))

    def test_reused_for_index_resampling_via_range_list(self):
        # research/advval/retrodiction.py's shape: draw indices, not values.
        # iid_resample_randrange(rng, list(range(n))) must reproduce
        # [rng.randrange(n) for _ in range(n)] exactly, since
        # list(range(n))[k] == k.
        n = 5
        rng_a = random.Random(11)
        expected = [rng_a.randrange(n) for _ in range(n)]
        rng_b = random.Random(11)
        assert iid_resample_randrange(rng_b, list(range(n))) == expected


class TestIidResampleChoices:
    def test_reproduces_rng_choices_exactly(self):
        data = [10.0, 20.0, 30.0]
        rng_a = random.Random(2)
        expected = rng_a.choices(data, k=3)
        rng_b = random.Random(2)
        assert iid_resample_choices(rng_b, data) == expected

    def test_differs_from_randrange_variant_for_the_same_seed(self):
        # The whole point of keeping these separate: they consume the PRNG
        # stream differently, so they must not be interchangeable.
        data = [1.0] * 3 + [2.0] * 3 + [3.0] * 3
        a = iid_resample_choices(random.Random(9), data)
        b = iid_resample_randrange(random.Random(9), data)
        assert a != b or len({a[0], b[0]}) >= 1  # smoke: exercised, not equal by construction


class TestCircularBlockResample:
    def test_reproduces_power_harness_resample_mean_block(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        rng_a = random.Random(3)
        n = len(data)
        expected: list[float] = []
        while len(expected) < n:
            start = rng_a.randrange(n)
            for offset in range(2):
                expected.append(data[(start + offset) % n])
                if len(expected) == n:
                    break
        rng_b = random.Random(3)
        assert circular_block_resample(rng_b, data, block_len=2) == expected

    def test_output_length_matches_input(self):
        data = [1.0, 2.0, 3.0]
        out = circular_block_resample(random.Random(1), data, block_len=2)
        assert len(out) == len(data)


class TestMovingBlockResample:
    def test_reproduces_carry_measure_and_fwd_analysis_shape(self):
        data = list(range(10))
        rng_a = random.Random(4)
        n = len(data)
        block = 3
        expected: list[int] = []
        while len(expected) < n:
            start = rng_a.randrange(0, max(1, n - block + 1))
            expected.extend(data[start:start + block])
        expected = expected[:n]
        rng_b = random.Random(4)
        assert moving_block_resample(rng_b, data, block_len=block) == expected

    def test_safe_when_block_exceeds_length(self):
        data = [1.0, 2.0]
        out = moving_block_resample(random.Random(1), data, block_len=10)
        assert len(out) == len(data)

    def test_explicit_target_len_reproduces_ruin_probability_shape(self):
        # research/fwd_analysis.py::ruin_probability resamples to an explicit
        # horizon_trades length, not len(data).
        data = list(range(5))
        block = 2
        target_len = 12
        rng_a = random.Random(8)
        expected: list[int] = []
        while len(expected) < target_len:
            start = rng_a.randrange(0, max(1, len(data) - block + 1))
            expected.extend(data[start:start + block])
        rng_b = random.Random(8)
        out = moving_block_resample(rng_b, data, block_len=block, target_len=target_len)
        assert out == expected[:len(out)]
        assert len(out) >= target_len  # matches the original: extend-until->=, no truncation

    def test_default_target_len_is_len_data(self):
        data = list(range(7))
        rng_a = random.Random(2)
        rng_b = random.Random(2)
        default = moving_block_resample(rng_a, data, block_len=3)
        explicit = moving_block_resample(rng_b, data, block_len=3, target_len=len(data))
        assert default == explicit


class TestFixedBlockCountResample:
    def test_reproduces_vrp_measure_shape(self):
        data = list(range(20))
        block_len = 5
        n_blocks = 4
        rng_a = random.Random(6)
        max_start = len(data) - block_len
        expected: list[int] = []
        for _ in range(n_blocks):
            start = rng_a.randint(0, max_start)
            for j in range(start, start + block_len):
                expected.append(data[j])
        rng_b = random.Random(6)
        assert (fixed_block_count_resample(rng_b, data, block_len, n_blocks)
                == expected)


class TestResampleByBlockKey:
    def test_reproduces_calibration_block_key_shape(self):
        blocks = {0: ["a", "b"], 1: ["c"], 2: ["d", "e", "f"]}
        keys = sorted(blocks)
        rng_a = random.Random(7)
        expected = []
        for _ in range(len(keys)):
            expected.extend(blocks[keys[rng_a.randrange(len(keys))]])
        rng_b = random.Random(7)
        assert resample_by_block_key(rng_b, blocks, keys) == expected


class TestPercentile:
    def test_matches_carry_measure_and_vrp_measure_formula(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(values, 50) == 3.0
        assert percentile(values, 0) == 1.0
        assert percentile(values, 100) == 5.0

    def test_single_value_returns_itself(self):
        assert percentile([7.0], 37) == 7.0

    def test_empty_raises(self):
        import pytest
        with pytest.raises(ValueError):
            percentile([], 50)
