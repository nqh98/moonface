import random

from moonface.models.engine.moe.nulls import iid_shuffle, phase_randomize, sign_flip


def test_iid_shuffle_preserves_multiset_and_length():
    rng = random.Random(0)
    src = {"A": [0.1, -0.2, 0.3, 0.0, 0.5]}
    out = iid_shuffle(src, rng)
    assert sorted(out["A"]) == sorted(src["A"])
    assert len(out["A"]) == len(src["A"])
    assert out["A"] != src["A"]


def test_sign_flip_preserves_absolute_values():
    rng = random.Random(1)
    src = {"A": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
    out = sign_flip(src, rng)
    assert sorted(abs(x) for x in out["A"]) == sorted(src["A"])
    assert any(x < 0 for x in out["A"])


def test_phase_randomize_is_rotation():
    rng = random.Random(2)
    src = {"A": [1.0, 2.0, 3.0, 4.0]}
    out = phase_randomize(src, rng)
    assert sorted(out["A"]) == sorted(src["A"])
    joined = out["A"] + out["A"]
    assert any(joined[i : i + 4] == [1.0, 2.0, 3.0, 4.0] for i in range(4))
