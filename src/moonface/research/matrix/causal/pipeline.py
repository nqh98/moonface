from __future__ import annotations

import math
from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.research.matrix.causal.features import CausalFeatureExtractor
from moonface.research.matrix.causal.gmm import CausalGMM
from moonface.research.matrix.causal.scaler import CausalStandardScaler
from moonface.research.matrix.causal.windows import walk_windows


@dataclass(frozen=True)
class RegimeInference:
    window_index: int
    bar_index: int
    test_ts_ms: int
    state_probs: tuple[float, ...]
    entropy: float
    top_state: int


@dataclass(frozen=True)
class WindowReport:
    window_index: int
    train_loglik: float
    n_test: int
    occupancy: tuple[float, ...]


def _entropy(p: tuple[float, ...]) -> float:
    return -sum(x * math.log(x) for x in p if x > 0.0)


def run_pipeline(candles: list[Candle], funding: list[float | None], *,
                 train_bars: int, test_bars: int, step_bars: int, gap_bars: int,
                 k: int, seed: int, extractor: CausalFeatureExtractor | None = None
                 ) -> tuple[list[RegimeInference], list[WindowReport]]:
    """Rolling firewall: per window, re-initialize a fresh scaler + GMM (no state
    carry-over), fit both on TRAIN features only, then emit predict_proba state
    vectors on the embargoed TEST block. Read-only; no gates, no naming."""
    extractor = extractor or CausalFeatureExtractor()
    n = len(candles)
    feats = {i: extractor.extract(candles, funding, i)
             for i in range(extractor.warmup, n)}
    inferences: list[RegimeInference] = []
    reports: list[WindowReport] = []
    for w in walk_windows(n, train_bars, test_bars, step_bars, gap_bars):
        if w.train_lo < extractor.warmup:
            continue
        train_X = [feats[i] for i in range(w.train_lo, w.train_hi)]
        scaler = CausalStandardScaler().fit(train_X)
        gmm = CausalGMM(k, seed=seed + w.index).fit(scaler.transform(train_X))
        counts = [0] * k
        for i in range(w.test_lo, w.test_hi):
            probs = gmm.predict_proba(scaler.transform([feats[i]]))[0]
            top = max(range(k), key=lambda c: probs[c])
            counts[top] += 1
            inferences.append(RegimeInference(
                window_index=w.index, bar_index=i,
                test_ts_ms=candles[i].timestamp_ms, state_probs=probs,
                entropy=_entropy(probs), top_state=top))
        n_test = w.test_hi - w.test_lo
        reports.append(WindowReport(
            window_index=w.index, train_loglik=gmm.loglik, n_test=n_test,
            occupancy=tuple(c / n_test for c in counts)))
    return inferences, reports
