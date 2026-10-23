"""Time-structure-preserving null calibration.

microscope.events.null_calibration shuffles labels row-wise. That was
defensible there: its labels were per-symbol, so each row carried its own
draw. Here the label is market-level and derived from a rolling 60-bar window,
so it is strongly autocorrelated -- labels arrive in long runs. Row-wise
shuffling destroys those runs, shrinks the null effect distribution, and makes
it too easy to beat. A null that cannot reproduce the structure of the real
thing is not a null; that is the vol_compression failure mode in a new costume.

So the primary null permutes the label *time series* in blocks, preserving run
length, and re-derives each event's label from the permuted series."""
from __future__ import annotations

import random

from moonface.research.microscope.events import effect_size

BLOCK = 30          # bars per permutation block -- FROZEN
N_SHUFFLES = 200


def circular_block_permute(seq: list, block: int,
                           rng: random.Random) -> list:
    """Rotate by a random offset, cut into `block`-sized chunks, shuffle the
    chunks, concatenate. Preserves the multiset and, for block > 1, the run
    structure inside each chunk."""
    n = len(seq)
    if n == 0:
        return []
    offset = rng.randrange(n)
    rotated = seq[offset:] + seq[:offset]
    chunks = [rotated[i:i + block] for i in range(0, n, block)]
    rng.shuffle(chunks)
    return [x for chunk in chunks for x in chunk][:n]


def block_null_calibration(outcomes: list[dict], bar_labels: list[str],
                           timestamps: list[int], seed: int = 0,
                           block: int = BLOCK,
                           n_shuffles: int = N_SHUFFLES) -> dict:
    """Re-run the effect with the bar-level label series block-permuted.

    A real conditional effect must beat this distribution. One that survives
    permutation is a selection artifact -- the vol_compression lesson made
    permanent: a valid effect must FAIL on a null."""
    index = {ts: i for i, ts in enumerate(timestamps)}
    real = effect_size(outcomes)
    rng = random.Random(seed)
    null_effects: list[float] = []
    beaten = 0
    for _ in range(n_shuffles):
        permuted = circular_block_permute(bar_labels, block, rng)
        rows = [{**r, "label": permuted[index[r["ts_ms"]]]} for r in outcomes]
        e = effect_size(rows)
        null_effects.append(e)
        if real > e:
            beaten += 1
    null_effects.sort()
    p95 = null_effects[int(0.95 * n_shuffles)] if n_shuffles else 0.0
    verdict = ("EXCEEDS_NULL" if real > p95 and real > 0.0
               else "INDISTINGUISHABLE_FROM_NULL")
    return {"real_effect": round(real, 4), "null_p95": round(p95, 4),
            "pct_beaten": round(beaten / n_shuffles, 4) if n_shuffles else 0.0,
            "verdict": verdict}
