"""Join features + label into Sample rows, keeping only fully-populated bars.

The optional HTF/funding/positioning/cross-sectional features are computed here
because this is where the aligned series live. A bar is kept only when every
frozen feature in FEATURE_NAMES and the label are present."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.research.pathsig.features import (FEATURE_NAMES,
                                                build_feature_rows, to_vector,
                                                zscore)
from moonface.research.pathsig.htf import align_htf_index
from moonface.research.pathsig.labels import PathLabel, build_labels

H4_MS = 14_400_000
D1_MS = 86_400_000
W1_MS = 604_800_000


def _slope(values: list[float | None], i: int, n: int) -> float | None:
    if i - n < 0 or values[i] is None or values[i - n] is None:
        return None
    return values[i] - values[i - n]


def build_dataset(bundle: DataBundle, h: int, atr_period: int,
                  xs_ret_rank: list[float | None],
                  xs_funding_rank: list[float | None],
                  d1_candles=None, w1_candles=None) -> list["Sample"]:
    """One asset -> list of complete Samples. d1_candles/w1_candles are the same
    asset's daily/weekly series for the HTF block; when None those features are
    treated as missing and every row is dropped (so HTF series are required for
    a usable dataset, by design)."""
    candles = bundle.candles
    n = len(candles)
    base = build_feature_rows(candles, atr_period)
    labels = build_labels(candles, h, atr_period)
    funding = bundle.funding or [None] * n
    oi = bundle.feature or [None] * n

    d1_idx = (align_htf_index(candles, d1_candles, H4_MS, D1_MS)
              if d1_candles else [None] * n)
    w1_idx = (align_htf_index(candles, w1_candles, H4_MS, W1_MS)
              if w1_candles else [None] * n)

    samples: list[Sample] = []
    for i in range(n):
        if base[i] is None or labels[i] is None:
            continue
        row = dict(base[i])
        row["htf_d1_ret_1"] = _d1_ret(d1_candles, d1_idx, i, 1)
        row["htf_d1_rvol_14"] = _d1_rvol(d1_candles, d1_idx, i, 14)
        row["htf_w1_ret_1"] = _d1_ret(w1_candles, w1_idx, i, 1)
        row["funding_level"] = funding[i]
        row["funding_slope_8"] = _slope(funding, i, 8)
        row["oi_z"] = zscore(oi, i, 180) if oi[i] is not None else None
        row["taker_z"] = zscore(oi, i, 180) if oi[i] is not None else None
        row["xs_ret_rank"] = xs_ret_rank[i]
        row["xs_funding_rank"] = xs_funding_rank[i]
        if any(row.get(name) is None for name in FEATURE_NAMES):
            continue
        samples.append(Sample(index=i, timestamp_ms=candles[i].timestamp_ms,
                              x=to_vector(row), label=labels[i]))
    return samples


def _d1_ret(d1, d1_idx, i, n):
    if not d1 or d1_idx[i] is None or d1_idx[i] - n < 0:
        return None
    j = d1_idx[i]
    prev = d1[j - n].close
    return d1[j].close / prev - 1.0 if prev > 0 else None


def _d1_rvol(d1, d1_idx, i, n):
    from statistics import pstdev
    if not d1 or d1_idx[i] is None or d1_idx[i] - n < 0:
        return None
    j = d1_idx[i]
    rets = []
    for k in range(j - n + 1, j + 1):
        p = d1[k - 1].close
        if p > 0:
            rets.append(d1[k].close / p - 1.0)
    return pstdev(rets) if len(rets) >= 2 else None


@dataclass(frozen=True)
class Sample:
    index: int
    timestamp_ms: int
    x: list[float]
    label: PathLabel
