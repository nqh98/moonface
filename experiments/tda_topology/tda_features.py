"""Cross-sectional correlation topology.

Persistent homology reads the correlation matrix at every threshold at once,
which is the whole reason this instrument exists: the source document warns
that a graph threshold is a large degree of freedom (its 13.5) and then picks
top-k edges anyway (its 14). Persistence *is* "how many thresholds does this
structure survive", so there is no threshold to tune.

Everything here is causal: a bar's features come from its trailing window and
from the immediately preceding bar's diagram, never from the future."""
from __future__ import annotations

import math

import numpy as np
from ripser import ripser
from scipy.optimize import linear_sum_assignment

W = 60                  # trailing window in bars (10 days at 4h) -- FROZEN
XS_MIN_ASSETS = 8       # cross-section floor
MAXDIM = 1              # H0 and H1 only; H2 is costly and meaningless at 17 pts

FEATURE_KEYS = ("pers_entropy_h0", "pers_entropy_h1",
                "total_pers_h0", "total_pers_h1",
                "landscape_l1_h1", "landscape_l2_h1",
                "wasserstein_dist")


def _ranks(xs: list[float]) -> list[float]:
    """Average ranks, ties shared -- the rank transform Spearman needs."""
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0.0 or vb <= 0.0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def spearman_corr(mat: list[list[float]]) -> list[list[float]]:
    """Spearman correlation across rows (rows = assets, cols = time).
    Spearman per source document 14 (`rolling Spearman correlation`)."""
    ranks = [_ranks(row) for row in mat]
    m = len(ranks)
    out = [[1.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            r = _pearson(ranks[i], ranks[j])
            out[i][j] = out[j][i] = r
    return out


def corr_distance(rho: list[list[float]]) -> list[list[float]]:
    """d_ij = sqrt(2(1 - rho_ij)) -- a true metric on correlation, mapping
    rho=1 to 0 and rho=-1 to 2."""
    m = len(rho)
    out = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(m):
            r = min(1.0, max(-1.0, rho[i][j]))
            out[i][j] = math.sqrt(2.0 * (1.0 - r))
    return out


def persistence_diagrams(dist: list[list[float]], maxdim: int = MAXDIM
                         ) -> tuple[list[tuple[float, float]],
                                    list[tuple[float, float]]]:
    """Vietoris-Rips H0/H1 as finite (birth, death) pairs.

    H0's one infinite class (the component that never dies) is dropped: it is
    present in every diagram and carries no information."""
    d = np.array(dist, dtype=float)
    dgms = ripser(d, distance_matrix=True, maxdim=maxdim)["dgms"]
    h0 = [(float(b), float(x)) for b, x in dgms[0] if np.isfinite(x)]
    h1 = [(float(b), float(x)) for b, x in dgms[1] if np.isfinite(x)]
    return h0, h1


def persistence_entropy(dgm: list[tuple[float, float]]) -> float | None:
    """Shannon entropy of normalized lifetimes. None for an empty diagram or
    one with no total lifetime -- there is no distribution to measure."""
    lifetimes = [d - b for b, d in dgm if d > b]
    total = sum(lifetimes)
    if not lifetimes or total <= 0.0:
        return None
    ent = 0.0
    for x in lifetimes:
        p = x / total
        ent -= p * math.log(p)
    return ent


def total_persistence(dgm: list[tuple[float, float]]) -> float:
    return sum(d - b for b, d in dgm)


def landscape_norms(dgm: list[tuple[float, float]],
                    n_grid: int = 200) -> tuple[float, float]:
    """(L1, L2) norms of the first persistence landscape -- the Gidea-Katz
    readout. lambda_1(x) = max_i max(0, min(x - b_i, d_i - x)), integrated by
    trapezoid over the diagram's support."""
    if not dgm:
        return 0.0, 0.0
    lo = min(b for b, _ in dgm)
    hi = max(d for _, d in dgm)
    if hi <= lo:
        return 0.0, 0.0
    step = (hi - lo) / (n_grid - 1)
    vals = []
    for k in range(n_grid):
        x = lo + k * step
        vals.append(max([max(0.0, min(x - b, d - x)) for b, d in dgm]))
    l1 = 0.0
    l2sq = 0.0
    for k in range(n_grid - 1):
        l1 += 0.5 * (vals[k] + vals[k + 1]) * step
        l2sq += 0.5 * (vals[k] ** 2 + vals[k + 1] ** 2) * step
    return l1, math.sqrt(l2sq)


_UNREACHABLE = 1e12


def wasserstein1(a: list[tuple[float, float]],
                 b: list[tuple[float, float]]) -> float:
    """1-Wasserstein distance between diagrams under the L-infinity ground
    metric, solved as optimal assignment.

    Unmatched points pay their projection to the diagonal, (d - b)/2. The
    bottom-right block is diagonal-to-diagonal and free."""
    n, m = len(a), len(b)
    if n == 0 and m == 0:
        return 0.0
    size = n + m
    cost = [[0.0] * size for _ in range(size)]
    for i in range(n):
        for j in range(m):
            cost[i][j] = max(abs(a[i][0] - b[j][0]), abs(a[i][1] - b[j][1]))
        for j in range(m, size):
            cost[i][j] = (a[i][1] - a[i][0]) / 2.0 if j - m == i else _UNREACHABLE
    for i in range(n, size):
        for j in range(m):
            cost[i][j] = (b[j][1] - b[j][0]) / 2.0 if i - n == j else _UNREACHABLE
        for j in range(m, size):
            cost[i][j] = 0.0
    rows, cols = linear_sum_assignment(np.array(cost))
    return float(sum(cost[i][j] for i, j in zip(rows, cols)))


def build_features(returns: dict[str, list[float | None]], n_bars: int,
                   w: int = W, min_assets: int = XS_MIN_ASSETS
                   ) -> list[dict[str, float | None]]:
    """Seven causal topology features per bar.

    A bar with fewer than `min_assets` complete trailing windows emits all
    None and becomes UNLABELED downstream. `wasserstein_dist` needs bar t-1 to
    have a diagram; when it does not, the feature is None rather than reaching
    further back -- comparing across a gap of unknown length would make the
    same feature mean different things at different bars (spec 3.2)."""
    out = [dict.fromkeys(FEATURE_KEYS) for _ in range(n_bars)]
    prev_h1: list[tuple[float, float]] | None = None
    prev_t = -1
    for t in range(w - 1, n_bars):
        window: list[list[float]] = []
        for series in returns.values():
            chunk = series[t - w + 1:t + 1]
            if len(chunk) == w and all(v is not None for v in chunk):
                window.append([float(v) for v in chunk])
        if len(window) < min_assets:
            continue
        h0, h1 = persistence_diagrams(corr_distance(spearman_corr(window)))
        row = out[t]
        row["pers_entropy_h0"] = persistence_entropy(h0)
        row["pers_entropy_h1"] = persistence_entropy(h1)
        row["total_pers_h0"] = total_persistence(h0)
        row["total_pers_h1"] = total_persistence(h1)
        l1, l2 = landscape_norms(h1)
        row["landscape_l1_h1"] = l1
        row["landscape_l2_h1"] = l2
        if prev_h1 is not None and prev_t == t - 1:
            row["wasserstein_dist"] = wasserstein1(prev_h1, h1)
        prev_h1, prev_t = h1, t
    return out
