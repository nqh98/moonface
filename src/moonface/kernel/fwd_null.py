# src/moonface/research/fwd_null.py
"""Per-segment funding-shuffle null for the calibration guard (the
vol_compression lesson: a valid gate must FAIL on null data). Shuffling
funding within contiguous non-None segments destroys the funding->price
alignment while preserving the marginal distribution and the gap structure;
missing periods stay missing — never interpolated or zero-filled."""
from __future__ import annotations

import random


def shuffle_funding_segments(funding: list[float | None],
                             seed: int) -> list[float | None]:
    rng = random.Random(seed)
    out = list(funding)
    i, n = 0, len(out)
    while i < n:
        if out[i] is None:
            i += 1
            continue
        j = i
        while j < n and out[j] is not None:
            j += 1
        seg = out[i:j]
        rng.shuffle(seg)
        out[i:j] = seg
        i = j
    return out
