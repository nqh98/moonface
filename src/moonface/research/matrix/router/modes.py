from __future__ import annotations

import math

from moonface.core.models import Candle
from moonface.research.matrix.baselines.strategies import DONCHIAN_N, _signal
from moonface.research.matrix.causal.features import CausalFeatureExtractor
from moonface.research.matrix.causal.gmm import CausalGMM
from moonface.research.matrix.causal.scaler import CausalStandardScaler
from moonface.research.matrix.causal.windows import walk_windows
from moonface.research.matrix.router.semantics import (
    ENTROPY_FREEZE,
    apply_entropy_override,
    rank_modes,
)


def _argmax(probs: tuple[float, ...]) -> int:
    return max(range(len(probs)), key=lambda state: probs[state])


def _entropy(probs: tuple[float, ...]) -> float:
    return -sum(prob * math.log(prob) for prob in probs if prob > 0.0)


def build_bar_modes(
    candles: list[Candle],
    funding: list[float | None],
    *,
    n: int = DONCHIAN_N,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    gap_bars: int,
    k: int,
    seed: int,
    entropy_freeze: float = ENTROPY_FREEZE,
    extractor: CausalFeatureExtractor | None = None,
) -> dict[int, int]:
    extractor = extractor or CausalFeatureExtractor()
    nbars = len(candles)
    feats = {
        i: extractor.extract(candles, funding, i)
        for i in range(extractor.warmup, nbars)
    }
    modes: dict[int, int] = {}
    for window in walk_windows(nbars, train_bars, test_bars, step_bars, gap_bars):
        if window.train_lo < extractor.warmup:
            continue
        train_X = [feats[i] for i in range(window.train_lo, window.train_hi)]
        scaler = CausalStandardScaler().fit(train_X)
        gmm = CausalGMM(k, seed=seed + window.index).fit(scaler.transform(train_X))
        sums = [0.0] * k
        counts = [0] * k
        for i in range(window.train_lo, window.train_hi - 1):
            side = _signal(candles, i, n)
            cur = candles[i].close
            if side == 0 or cur <= 0.0:
                continue
            top = _argmax(gmm.predict_proba(scaler.transform([feats[i]]))[0])
            sums[top] += side * (candles[i + 1].close - cur) / cur
            counts[top] += 1
        scores = {
            state: (sums[state] / counts[state] if counts[state] else None)
            for state in range(k)
        }
        state_modes = rank_modes(scores, k)
        for i in range(window.test_lo, window.test_hi):
            probs = gmm.predict_proba(scaler.transform([feats[i]]))[0]
            modes[i] = apply_entropy_override(
                state_modes[_argmax(probs)],
                _entropy(probs),
                entropy_freeze,
            )
    return modes
