from __future__ import annotations

from statistics import fmean, pstdev

STD_FLOOR = 1e-9


class CausalStandardScaler:
    """Standardize with mean/std computed from TRAIN rows only; `transform` applies
    those frozen stats to any matrix (train or test)."""

    def __init__(self, std_floor: float = STD_FLOOR) -> None:
        self.means: list[float] | None = None
        self.stds: list[float] | None = None
        self.std_floor = std_floor

    def fit(self, X: list[list[float]]) -> "CausalStandardScaler":
        d = len(X[0])
        self.means = [fmean([row[j] for row in X]) for j in range(d)]
        self.stds = [max(pstdev([row[j] for row in X]), self.std_floor)
                     for j in range(d)]
        return self

    def transform(self, X: list[list[float]]) -> list[list[float]]:
        assert self.means is not None and self.stds is not None
        return [[(row[j] - self.means[j]) / self.stds[j]
                 for j in range(len(row))] for row in X]
