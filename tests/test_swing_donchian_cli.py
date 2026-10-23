from tools.engine.swing_donchian import render_result, ResultInput


def test_render_result_states_pass_when_verdict_passed():
    inp = ResultInput(
        symbol="BTCUSDT", interval="4h",
        passed=True, reasons=["all thresholds met"],
        metrics={"expectancy_r": 0.08, "profit_factor": 1.3, "mar": 0.7,
                 "max_dd_r": -22.0, "robust_frac": 0.7},
        n_windows=4, chosen_summary="entry_n/trail_n mode = 20/10",
    )
    md = render_result(inp)
    assert "# Donchian Walk-Forward Result" in md
    assert "PASS" in md
    assert "0.08" in md and "1.3" in md


def test_render_result_states_fail_when_verdict_failed_and_lists_reasons():
    inp = ResultInput(
        symbol="BTCUSDT", interval="4h",
        passed=False, reasons=["profit factor 0.9 < 1.2", "robust in 40% of windows < 60%"],
        metrics={"expectancy_r": 0.01, "profit_factor": 0.9, "mar": 0.1,
                 "max_dd_r": -45.0, "robust_frac": 0.4},
        n_windows=4, chosen_summary="entry_n/trail_n mode = 20/10",
    )
    md = render_result(inp)
    assert "FAIL" in md
    assert "profit factor 0.9" in md
    assert "honest" in md.lower() or "no deployable" in md.lower()
