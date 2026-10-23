"""Tests for Step-0 correlation screen (Task 5)."""
from __future__ import annotations

from moonface.research.portfolio.correlation import (pearson, corr_matrix,
                                                     select_basket, step0_screen,
                                                     CORR_CUTOFF, MAX_BASKET, MIN_BASKET)


def test_pearson_basic():
    assert abs(pearson([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3, 4], [-1, -2, -3, -4]) + 1.0) < 1e-9
    assert abs(pearson([1, 2, 3, 4], [4, 1, 2, 3])) < 0.9  # weak


def test_corr_matrix_symmetric():
    series = [[1, 2, 3], [3, 2, 1], [1, 3, 2]]
    m = corr_matrix(series)
    assert len(m) == 3
    for i in range(3):
        for j in range(3):
            assert abs(m[i][j] - m[j][i]) < 1e-9
            assert m[i][i] >= 0.999


def test_select_basket_enforces_cutoff():
    comps = ["a", "b", "c"]
    # a,b perfectly correlated (rho=1); c uncorrelated to both
    series = [[1, 2, 3, 4, 5], [2, 4, 6, 8, 10], [5, 1, 4, 2, 3]]
    basket = select_basket(comps, series)
    assert "a" in basket
    assert ("b" not in basket) or ("a" not in basket)  # at most one of {a,b}
    assert all(abs(pearson(series[comps.index(basket[0])], series[compi])) <= CORR_CUTOFF + 1e-9
               for compi in [comps.index(c) for c in basket[1:]])


def test_step0_screen_thesis_dead_when_all_correlated():
    comps = ["a", "b", "c"]
    series = [[1, 2, 3, 4], [2, 4, 6, 8], [3, 6, 9, 12]]  # all rho=1
    res = step0_screen(comps, series)
    assert res["verdict"] == "thesis_dead"
    assert res["basket_size"] < MIN_BASKET


def test_constants_frozen():
    assert MAX_BASKET == 8 and CORR_CUTOFF == 0.5 and MIN_BASKET == 2
