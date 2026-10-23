from moonface.research.drift_basket.basket import (
    BasketParams,
    inverse_vol_weights,
    rolling_beta,
    simulate_basket,
)

DAY = 86_400_000


def test_inverse_vol_weights_normalized_and_drops_zero():
    w = inverse_vol_weights({"A": 0.01, "B": 0.02, "C": 0.0})
    assert "C" not in w
    assert abs(sum(w.values()) - 1.0) < 1e-12
    assert w["A"] > w["B"]                       # lower vol -> higher weight


def test_rolling_beta_recovers_known_slope():
    btc = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03]
    book = [2.0 * x for x in btc]                # exact beta 2.0
    assert abs(rolling_beta(book, btc, k=6, window=6) - 2.0) < 1e-9


def test_beta_hedge_zeroes_a_pure_beta_leg():
    # One asset that is exactly BTC (pure beta, zero idiosyncratic drift),
    # always active. After hedging, the leveraged portfolio return should be ~0.
    days = [i * DAY for i in range(40)]
    btc_path = [0.01 if i % 2 == 0 else -0.011 for i in range(40)]
    btc_rets = {days[i]: btc_path[i] for i in range(40)}
    daily_rets = {"X": dict(btc_rets)}           # X == BTC exactly
    daily_flags = {"X": {d: True for d in days}}
    universe = {d: ["X"] for d in days}
    out = simulate_basket(days, universe, daily_flags, daily_rets, btc_rets,
                          funding={}, params=BasketParams())
    # after warmup the hedge removes beta -> residual returns near zero
    tail = [r for _, r in out[35:]]
    assert max(abs(r) for r in tail) < 1e-3


def test_idiosyncratic_drift_survives_hedge():
    # Asset Y has a steady idiosyncratic drift uncorrelated with BTC noise.
    days = [i * DAY for i in range(60)]
    btc_path = [0.02 if i % 2 == 0 else -0.02 for i in range(60)]
    btc_rets = {days[i]: btc_path[i] for i in range(60)}
    y = [0.003 + (0.001 if i % 3 == 0 else -0.001) for i in range(60)]
    daily_rets = {"Y": {days[i]: y[i] for i in range(60)}}
    daily_flags = {"Y": {d: True for d in days}}
    universe = {d: ["Y"] for d in days}
    out = simulate_basket(days, universe, daily_flags, daily_rets, btc_rets,
                          funding={}, params=BasketParams())
    mean_tail = sum(r for _, r in out[30:]) / len(out[30:])
    assert mean_tail > 0.0                        # positive residual drift remains


def test_funding_reduces_long_return():
    days = [i * DAY for i in range(40)]
    rets = {"Z": {d: (0.01 if i % 2 == 0 else 0.005) for i, d in enumerate(days)}}
    flags = {"Z": {d: True for d in days}}
    uni = {d: ["Z"] for d in days}
    btc = {d: 0.0 for d in days}
    no_fund = simulate_basket(days, uni, flags, rets, btc, {}, BasketParams())
    fund = simulate_basket(days, uni, flags, rets, btc,
                           {"Z": {d: 0.002 for d in days}}, BasketParams())
    assert sum(r for _, r in fund[20:]) < sum(r for _, r in no_fund[20:])
