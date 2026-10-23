from moonface.research.funding_cost import held_funding_rates, funding_cost_r, funding_cost_pct


def test_held_funding_rates_picks_strictly_inside_hold_window():
    # funding prints at 8h cadence: t0, t0+8h, t0+16h ...
    points = [(0, 0.0001), (28_800_000, 0.0002), (57_600_000, 0.0003)]
    # hold open during (entry_ms, exit_ms]; a rate whose ts == entry_ms is NOT yet paid
    held = held_funding_rates(points, entry_ms=10_000_000, exit_ms=57_600_000)
    assert [r for _, r in held] == [0.0002, 0.0003]


def test_funding_cost_r_long_pays_positive_rate():
    # long pays positive funding: cost reduces R. risk = price distance for 1R.
    rates = [(0, 0.0010)]  # +0.10% once
    # funding paid = rate * notional. notional expressed per unit risk: cost_r = rate/risk_fraction_of_notional
    # Here we pass risk in price units; notional = entry (100), risk = 1 price unit => cost_r = 0.0010*100/1 = 0.1
    assert funding_cost_r(rates, side="BUY", risk=1.0, notional=100.0) == 0.1


def test_funding_cost_r_short_receives_positive_funding():
    # short receives positive funding (cost is negative, i.e. a credit)
    rates = [(0, 0.0010)]
    assert funding_cost_r(rates, side="SELL", risk=1.0, notional=100.0) == -0.1


def test_funding_cost_pct_sums_all_rates_signed_by_side():
    rates = [0.0005, -0.0003, 0.0002]
    # long pays net +; short receives net + (cost negative). Tolerance: the
    # primitive is an unrounded float sum, so compare by absolute difference.
    assert abs(funding_cost_pct(rates, side="BUY") - 0.0004) < 1e-9
    assert abs(funding_cost_pct(rates, side="SELL") - (-0.0004)) < 1e-9
