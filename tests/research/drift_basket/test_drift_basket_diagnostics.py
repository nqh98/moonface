from moonface.research.drift_basket.diagnostics import (
    cocrash_metrics,
    distinctness_correlation,
    pearson,
    trailing_return,
)

DAY = 86_400_000


def test_pearson_basic():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3], [6, 4, 2]) + 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0     # zero variance -> 0


def test_trailing_return_compounds_and_handles_gaps():
    rets = {2 * DAY: 0.1, 3 * DAY: 0.2}
    r = trailing_return(rets, 3 * DAY, days_back=2)
    assert abs(r - (1.1 * 1.2 - 1.0)) < 1e-9
    assert trailing_return({3 * DAY: 0.2}, 3 * DAY, days_back=2) is None  # gap


def test_distinctness_near_zero_when_flags_orthogonal_to_momentum():
    # Active flag alternates independently of the (monotone) momentum ranking.
    days = [i * DAY for i in range(5, 40)]
    syms = [f"S{j}" for j in range(8)]
    daily_rets = {s: {i * DAY: 0.001 * (j + 1) for i in range(40)}
                  for j, s in enumerate(syms)}      # constant per-sym mom rank
    universe_by_day = {d: syms for d in days}
    # flags depend only on the DAY parity, not the symbol's momentum rank
    daily_flags = {s: {d: ((d // DAY) % 2 == 0) for d in days} for s in syms}
    corr = distinctness_correlation(days, universe_by_day, daily_flags,
                                    daily_rets, mom_days=3)
    assert abs(corr) < 0.2


def test_distinctness_high_when_flags_track_momentum():
    days = [i * DAY for i in range(5, 40)]
    syms = [f"S{j}" for j in range(8)]
    daily_rets = {s: {i * DAY: 0.001 * (j + 1) for i in range(40)}
                  for j, s in enumerate(syms)}
    universe_by_day = {d: syms for d in days}
    # only the top-4 momentum symbols (S4..S7) are ever active
    daily_flags = {s: {d: (int(s[1:]) >= 4) for d in days} for s in syms}
    corr = distinctness_correlation(days, universe_by_day, daily_flags,
                                    daily_rets, mom_days=3)
    assert corr > 0.6


def test_cocrash_metrics_beta_and_tail_corr():
    btc = [0.01, -0.05, 0.02, -0.06, 0.03, -0.04, 0.01, -0.05, 0.02, -0.07]
    port = [0.5 * x for x in btc]                  # beta 0.5, perfectly correlated
    full_beta, tail_corr = cocrash_metrics(port, btc)
    assert abs(full_beta - 0.5) < 1e-9
    assert tail_corr > 0.99
