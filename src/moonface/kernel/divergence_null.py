"""Cross-coupling surrogate null for price_oi_divergence."""
from __future__ import annotations

import random

from moonface.core.bundle import DataBundle
from moonface.core.metrics import equity_summary
from moonface.research.ladder import SCREEN_FRACTION, r_stream
from moonface.kernel.spec import HypothesisSpec

NULL_ALPHA = 0.05
NULL_DRAWS = 200
NULL_BLOCK_LEN = 24
NULL_SEED = 20260708


def block_shuffle(feature: list, block_len: int, rng: random.Random) -> list:
    if block_len <= 0:
        raise ValueError(f"block_len must be positive, got {block_len}")
    blocks = [feature[i:i + block_len] for i in range(0, len(feature), block_len)]
    rng.shuffle(blocks)
    return [value for block in blocks for value in block]


def _holdout_mar(spec: HypothesisSpec, bundle: DataBundle,
                 fraction: float) -> float:
    split = int(len(bundle.candles) * fraction)
    stream = r_stream(spec, bundle)
    hold = equity_summary([(r, af) for i, r, af in stream if i >= split],
                          spec.fraction)
    return hold.mar


def surrogate_null(spec: HypothesisSpec, research: DataBundle, *,
                   draws: int = NULL_DRAWS, block_len: int = NULL_BLOCK_LEN,
                   fraction: float = SCREEN_FRACTION,
                   seed: int = NULL_SEED) -> dict:
    if research.feature is None:
        raise ValueError("surrogate_null requires an OI feature series")
    real_mar = _holdout_mar(spec, research, fraction)
    rng = random.Random(seed)
    ge = 0
    for _ in range(draws):
        shuffled = block_shuffle(research.feature, block_len, rng)
        null_bundle = DataBundle(
            candles=research.candles,
            funding=research.funding,
            basis=research.basis,
            feature=shuffled)
        if _holdout_mar(spec, null_bundle, fraction) >= real_mar:
            ge += 1
    p_value = (ge + 1) / (draws + 1)
    return {"real_mar": real_mar, "p_value": p_value,
            "passed": p_value < NULL_ALPHA and real_mar > 0.0,
            "draws": draws}
