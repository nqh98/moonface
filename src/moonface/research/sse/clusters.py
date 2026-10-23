from __future__ import annotations

import math
import random
from dataclasses import dataclass

UNLABELED = -1


@dataclass(frozen=True)
class ClusterModel:
    feature_names: tuple[str, ...]
    centroids: list[tuple[float, ...]]


def _row_vector(row: dict[str, float | None], feature_names: tuple[str, ...]) -> tuple[float, ...] | None:
    vals = [row.get(name) for name in feature_names]
    if any(v is None for v in vals):
        return None
    return tuple(float(v) for v in vals)


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def fit_kmeans(
    rows: list[dict[str, float | None]],
    *,
    feature_names: tuple[str, ...],
    fit_mask: list[bool],
    k: int = 4,
    seed: int = 1,
    max_iter: int = 100,
) -> ClusterModel:
    vectors = [_row_vector(row, feature_names) for row in rows]
    fit_vecs = [v for v, keep in zip(vectors, fit_mask) if keep and v is not None]
    if len(fit_vecs) < k:
        raise ValueError(f"need at least {k} complete rows to fit k-means")
    rng = random.Random(seed)
    centroids = [tuple(v) for v in rng.sample(fit_vecs, k)]
    for _ in range(max_iter):
        groups = [[] for _ in range(k)]
        for vec in fit_vecs:
            idx = min(range(k), key=lambda j: _distance(vec, centroids[j]))
            groups[idx].append(vec)
        new = []
        for j, group in enumerate(groups):
            if not group:
                new.append(centroids[j])
                continue
            new.append(tuple(sum(v[i] for v in group) / len(group) for i in range(len(group[0]))))
        if new == centroids:
            break
        centroids = new
    return ClusterModel(feature_names=feature_names, centroids=centroids)


def assign_clusters(rows: list[dict[str, float | None]], model: ClusterModel) -> list[int]:
    out: list[int] = []
    for row in rows:
        vec = _row_vector(row, model.feature_names)
        if vec is None:
            out.append(UNLABELED)
            continue
        out.append(min(range(len(model.centroids)), key=lambda j: _distance(vec, model.centroids[j])))
    return out

