from __future__ import annotations

import random


def iid_shuffle(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name, series in series_by_expert.items():
        copy = list(series)
        rng.shuffle(copy)
        out[name] = copy
    return out


def sign_flip(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    return {
        name: [(-value if rng.random() < 0.5 else value) for value in series]
        for name, series in series_by_expert.items()
    }


def phase_randomize(
    series_by_expert: dict[str, list[float]], rng: random.Random
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name, series in series_by_expert.items():
        n = len(series)
        if n == 0:
            out[name] = []
            continue
        k = rng.randrange(n)
        out[name] = series[k:] + series[:k]
    return out
