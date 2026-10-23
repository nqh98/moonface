"""Deterministic pure-stdlib gradient-boosted stumps for era discrimination.

The model is frozen and intentionally small: depth-1 trees only, no sampling,
no randomness, and no dependency beyond the standard library. Leaf values are
fit to the logistic gradient and stored already shrunk by `lr`, so prediction
is a plain additive score pass. This keeps the implementation stable for the
frozen adversarial-validation preregistration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def auc(scores: list[float], labels: list[int]) -> float:
    """Mann-Whitney AUC with midrank tie handling."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be binary 0/1")
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("auc needs both classes")

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        score = scores[order[i]]
        while j + 1 < len(order) and scores[order[j + 1]] == score:
            j += 1
        rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = rank
        i = j + 1

    pos_rank_sum = sum(rank for rank, label in zip(ranks, labels) if label == 1)
    return (pos_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


@dataclass(frozen=True)
class Stump:
    feature: int
    threshold: float
    left_val: float
    right_val: float


@dataclass(frozen=True)
class GbtModel:
    base: float
    stumps: tuple[Stump, ...]


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _best_stump(
    X: list[list[float]],
    grad: list[float],
    rows: list[int],
    sorted_rows: list[list[int]],
    min_leaf: int,
) -> Stump | None:
    best_gain = 0.0
    best: Stump | None = None
    n_rows = len(rows)
    row_set = set(rows)
    total_grad = sum(grad[r] for r in rows)

    for feature, order in enumerate(sorted_rows):
        seq = [r for r in order if r in row_set]
        if len(seq) < 2 * min_leaf:
            continue

        left_sum = 0.0
        for i in range(len(seq) - 1):
            row = seq[i]
            left_sum += grad[row]
            left_count = i + 1
            right_count = n_rows - left_count
            if left_count < min_leaf or right_count < min_leaf:
                continue

            left_x = X[row][feature]
            right_x = X[seq[i + 1]][feature]
            if left_x == right_x:
                continue

            right_sum = total_grad - left_sum
            gain = left_sum * left_sum / left_count + right_sum * right_sum / right_count
            if gain > best_gain:
                threshold = (left_x + right_x) / 2.0
                best_gain = gain
                best = Stump(
                    feature=feature,
                    threshold=threshold,
                    left_val=left_sum / left_count,
                    right_val=right_sum / right_count,
                )

    return best


def fit_gbt(
    X: list[list[float]],
    y: list[int],
    rounds: int = 200,
    lr: float = 0.1,
    min_leaf: int = 20,
) -> GbtModel:
    if len(X) != len(y):
        raise ValueError("X and y must have the same length")
    if any(label not in (0, 1) for label in y):
        raise ValueError("y must be binary 0/1")
    if not X:
        raise ValueError("fit_gbt needs at least one row")
    n_pos = sum(y)
    n_total = len(y)
    if n_pos == 0 or n_pos == n_total:
        raise ValueError("fit_gbt needs both classes")

    base = math.log((n_pos / n_total) / (1.0 - (n_pos / n_total)))
    n_features = len(X[0])
    sorted_rows = [sorted(range(n_total), key=lambda r, f=f: X[r][f])
                   for f in range(n_features)]
    scores = [base] * n_total
    rows = list(range(n_total))
    stumps: list[Stump] = []

    for _ in range(rounds):
        grad = [y[i] - _sigmoid(scores[i]) for i in range(n_total)]
        stump = _best_stump(X, grad, rows, sorted_rows, min_leaf)
        if stump is None:
            break

        scaled = Stump(
            feature=stump.feature,
            threshold=stump.threshold,
            left_val=stump.left_val * lr,
            right_val=stump.right_val * lr,
        )
        for i, row in enumerate(X):
            step = scaled.left_val if row[scaled.feature] <= scaled.threshold else scaled.right_val
            scores[i] += step
        stumps.append(scaled)

    return GbtModel(base=base, stumps=tuple(stumps))


def predict(model: GbtModel, X: list[list[float]]) -> list[float]:
    """Raw additive scores, monotone in probability."""
    out: list[float] = []
    for row in X:
        score = model.base
        for stump in model.stumps:
            score += stump.left_val if row[stump.feature] <= stump.threshold else stump.right_val
        out.append(score)
    return out


def block_folds(
    n: int,
    n_folds: int = 5,
    embargo: int = 90,
) -> list[tuple[list[int], list[int]]]:
    """Contiguous equal blocks with an embargo around each test block."""
    if n_folds <= 0:
        raise ValueError("n_folds must be positive")
    if n < 0:
        raise ValueError("n must be non-negative")
    if embargo < 0:
        raise ValueError("embargo must be non-negative")

    bounds = [round(k * n / n_folds) for k in range(n_folds + 1)]
    folds: list[tuple[list[int], list[int]]] = []
    for k in range(n_folds):
        lo = bounds[k]
        hi = bounds[k + 1]
        test = list(range(lo, hi))
        train = [
            i for i in range(n)
            if i < lo - embargo or i >= hi + embargo
        ]
        folds.append((train, test))
    return folds


def cv_auc(
    X: list[list[float]],
    y: list[int],
    n_folds: int = 5,
    embargo: int = 90,
    rounds: int = 200,
    lr: float = 0.1,
    min_leaf: int = 20,
) -> float:
    """Fold within each era separately, then pool test predictions for one AUC."""
    if len(X) != len(y):
        raise ValueError("X and y must have the same length")
    if any(label not in (0, 1) for label in y):
        raise ValueError("y must be binary 0/1")
    if len(set(y)) < 2:
        raise ValueError("cv_auc needs both classes")
    era0 = [i for i, label in enumerate(y) if label == 0]
    era1 = [i for i, label in enumerate(y) if label == 1]
    folds0 = block_folds(len(era0), n_folds=n_folds, embargo=embargo)
    folds1 = block_folds(len(era1), n_folds=n_folds, embargo=embargo)

    pooled_scores: list[float] = []
    pooled_labels: list[int] = []

    for k in range(n_folds):
        train_idx = [era0[i] for i in folds0[k][0]] + [era1[i] for i in folds1[k][0]]
        test_idx = [era0[i] for i in folds0[k][1]] + [era1[i] for i in folds1[k][1]]
        if not train_idx or not test_idx:
            raise ValueError("cv_auc needs enough data for every fold")

        X_train = [X[i] for i in train_idx]
        y_train = [y[i] for i in train_idx]
        if len(set(y_train)) < 2:
            continue
        model = fit_gbt(X_train, y_train, rounds=rounds, lr=lr, min_leaf=min_leaf)

        pooled_scores.extend(predict(model, [X[i] for i in test_idx]))
        pooled_labels.extend(y[i] for i in test_idx)

    if len(set(pooled_labels)) < 2:
        raise ValueError("cv_auc needs both classes")
    return auc(pooled_scores, pooled_labels)
