"""Step-0 correlation screen: keep a low-correlation basket (no holdout spent)."""
from __future__ import annotations

import math

MAX_BASKET = 8
CORR_CUTOFF = 0.5
MIN_BASKET = 2


def pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ax = a[:n]
    bx = b[:n]
    ma = sum(ax) / n
    mb = sum(bx) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ax, bx))
    da = math.sqrt(sum((x - ma) ** 2 for x in ax))
    db = math.sqrt(sum((y - mb) ** 2 for y in bx))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def corr_matrix(series: list[list[float]]) -> list[list[float]]:
    n = len(series)
    return [[pearson(series[i], series[j]) for j in range(n)] for i in range(n)]


def select_basket(components, returns_list, *, max_size=MAX_BASKET,
                  cutoff=CORR_CUTOFF, min_size=MIN_BASKET) -> list:
    """Greedy: walk components in order, keep one if |rho| to all kept <= cutoff."""
    kept_idx: list[int] = []
    for i in range(len(components)):
        if len(kept_idx) >= max_size:
            break
        if all(abs(pearson(returns_list[i], returns_list[k])) <= cutoff for k in kept_idx):
            kept_idx.append(i)
    return [components[i] for i in kept_idx]


def step0_screen(components, returns_list) -> dict:
    matrix = corr_matrix(returns_list)
    basket = select_basket(components, returns_list)
    return {
        "matrix": matrix,
        "basket": basket,
        "basket_size": len(basket),
        "verdict": "ok" if len(basket) >= MIN_BASKET else "thesis_dead",
    }
