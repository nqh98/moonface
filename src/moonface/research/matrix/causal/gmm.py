from __future__ import annotations

import math
import random
from statistics import pstdev

N_ITER = 100
TOL = 1e-4
N_INIT = 5
VARIANCE_FLOOR = 1e-6


def _log_gauss_diag(x: list[float], mean: list[float], var: list[float]) -> float:
    s = 0.0
    for xd, md, vd in zip(x, mean, var):
        s += math.log(2.0 * math.pi * vd) + (xd - md) ** 2 / vd
    return -0.5 * s


def _logsumexp(vals: list[float]) -> float:
    m = max(vals)
    return m + math.log(sum(math.exp(v - m) for v in vals))


class CausalGMM:
    """Diagonal-covariance Gaussian mixture via EM, pure stdlib. Deterministic:
    each restart is seeded from `seed`. `n_init` restarts keep the best log-likelihood."""

    def __init__(self, k: int, seed: int, n_iter: int = N_ITER, tol: float = TOL,
                 n_init: int = N_INIT, var_floor: float = VARIANCE_FLOOR) -> None:
        self.k = k
        self.seed = seed
        self.n_iter = n_iter
        self.tol = tol
        self.n_init = n_init
        self.var_floor = var_floor
        self.weights: list[float] | None = None
        self.means: list[list[float]] | None = None
        self.vars: list[list[float]] | None = None
        self.loglik: float | None = None

    def _init_params(self, X, rng):
        d = len(X[0])
        idx = rng.sample(range(len(X)), self.k)
        means = [list(X[i]) for i in idx]
        gvar = [max(pstdev([row[j] for row in X]) ** 2, self.var_floor)
                for j in range(d)]
        vars_ = [list(gvar) for _ in range(self.k)]
        weights = [1.0 / self.k] * self.k
        return weights, means, vars_

    def _em(self, X, rng):
        weights, means, vars_ = self._init_params(X, rng)
        n, d = len(X), len(X[0])
        prev_ll = None
        for _ in range(self.n_iter):
            resp, ll = [], 0.0
            for x in X:
                logp = [math.log(weights[c]) + _log_gauss_diag(x, means[c], vars_[c])
                        for c in range(self.k)]
                lse = _logsumexp(logp)
                ll += lse
                resp.append([math.exp(lp - lse) for lp in logp])
            for c in range(self.k):
                nk = sum(r[c] for r in resp)
                if nk <= 1e-12:
                    continue
                weights[c] = nk / n
                for j in range(d):
                    m = sum(resp[i][c] * X[i][j] for i in range(n)) / nk
                    means[c][j] = m
                    v = sum(resp[i][c] * (X[i][j] - m) ** 2 for i in range(n)) / nk
                    vars_[c][j] = max(v, self.var_floor)
            if prev_ll is not None and abs(ll - prev_ll) < self.tol:
                prev_ll = ll
                break
            prev_ll = ll
        return weights, means, vars_, prev_ll

    def fit(self, X: list[list[float]]) -> "CausalGMM":
        best = None
        for r in range(self.n_init):
            rng = random.Random(self.seed * 1000 + r)
            weights, means, vars_, ll = self._em(X, rng)
            if best is None or ll > best[3]:
                best = (weights, means, vars_, ll)
        self.weights, self.means, self.vars, self.loglik = best
        return self

    def _log_resp(self, x):
        return [math.log(self.weights[c]) + _log_gauss_diag(x, self.means[c],
                                                            self.vars[c])
                for c in range(self.k)]

    def predict_proba(self, X: list[list[float]]) -> list[tuple[float, ...]]:
        out = []
        for x in X:
            logp = self._log_resp(x)
            lse = _logsumexp(logp)
            out.append(tuple(math.exp(lp - lse) for lp in logp))
        return out

    def score(self, X: list[list[float]]) -> float:
        return sum(_logsumexp(self._log_resp(x)) for x in X) / len(X)
