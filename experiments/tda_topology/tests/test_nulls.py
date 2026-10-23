import random

from nulls import BLOCK, block_null_calibration, circular_block_permute


def test_block_one_is_a_permutation_of_the_input():
    seq = list(range(50))
    out = circular_block_permute(seq, 1, random.Random(0))
    assert sorted(out) == seq
    assert len(out) == len(seq)


def test_block_equal_to_length_is_a_rotation():
    seq = list(range(10))
    out = circular_block_permute(seq, len(seq), random.Random(3))
    assert sorted(out) == seq
    doubled = seq + seq
    assert any(doubled[i:i + len(seq)] == out for i in range(len(seq)))


def test_permutation_preserves_the_multiset_for_any_block():
    seq = ["A"] * 17 + ["B"] * 13 + ["C"] * 20
    for block in (1, 7, 30, 50):
        out = circular_block_permute(seq, block, random.Random(block))
        assert sorted(out) == sorted(seq)


def test_block_permutation_preserves_run_structure_better_than_shuffling():
    # A label series of long runs must keep long runs under block permutation,
    # while a plain shuffle destroys them. This is the whole point of BLOCK.
    seq = (["A"] * 100) + (["B"] * 100)

    def longest_run(xs):
        best = cur = 1
        for i in range(1, len(xs)):
            cur = cur + 1 if xs[i] == xs[i - 1] else 1
            best = max(best, cur)
        return best

    blocked = circular_block_permute(seq, BLOCK, random.Random(1))
    shuffled = circular_block_permute(seq, 1, random.Random(1))
    assert longest_run(blocked) >= BLOCK
    assert longest_run(shuffled) < BLOCK


def _outcomes(labels_by_bar, timestamps):
    # One event per bar, forward R equal to a constant per label.
    payoff = {"UP": 1.0, "DOWN": -1.0}
    return [{"symbol": "X", "ts_ms": ts, "direction": 1,
             "label": labels_by_bar[i], "fwd_r_12": payoff[labels_by_bar[i]]}
            for i, ts in enumerate(timestamps)]


def test_a_perfectly_separating_label_exceeds_the_null():
    timestamps = list(range(200))
    bar_labels = ["UP"] * 100 + ["DOWN"] * 100
    outcomes = _outcomes(bar_labels, timestamps)
    res = block_null_calibration(outcomes, bar_labels, timestamps,
                                 seed=0, block=1, n_shuffles=50)
    assert res["real_effect"] == 2.0
    assert res["verdict"] == "EXCEEDS_NULL"


def test_a_label_unrelated_to_outcome_is_indistinguishable_from_null():
    timestamps = list(range(200))
    bar_labels = ["UP" if i % 2 == 0 else "DOWN" for i in range(200)]
    rng = random.Random(7)
    outcomes = [{"symbol": "X", "ts_ms": ts, "direction": 1,
                 "label": bar_labels[i], "fwd_r_12": rng.gauss(0.0, 1.0)}
                for i, ts in enumerate(timestamps)]
    res = block_null_calibration(outcomes, bar_labels, timestamps,
                                 seed=0, block=1, n_shuffles=200)
    assert res["verdict"] == "INDISTINGUISHABLE_FROM_NULL"
