from moonface.research.btcspec.pipeline import freeze_candidates, render_result


def _result_row(label, verdict, sealed=None):
    return {"label": label, "timeframe": "4h", "family": "donchian_break",
            "params": {"n": 20}, "exit_name": "atr_trail",
            "exit_params": {"k_trail": 2.0, "max_bars": 60, "atr_period": 14},
            "h": 30, "group": "g", "axis": 1.0, "dsr": 0.2,
            "validate": {"robust_frac": 0.7, "agg_total_r": 5.0},
            "sealed": sealed, "verdict": verdict}


def test_freeze_candidates_keeps_only_frozen_keys():
    survivors = [{**_result_row("a", "x"), "selection": {"passed": True},
                  "metrics": {"total_r": 9}}]
    frozen = freeze_candidates(survivors)
    assert set(frozen[0]) == {"label", "timeframe", "family", "params", "exit_name",
                              "exit_params", "h", "group", "axis"}


def test_render_result_negative_when_no_accept():
    rows = [_result_row("a", "rejected")]
    md = render_result(rows, "2026-06-21T00:00:00Z", {"4h": "abcd"})
    assert "## Verdict: NEGATIVE" in md
    assert "PAPER ONLY" in md


def test_render_result_flags_paper_candidate():
    sealed = {"passed": True, "metrics": {"profit_factor": 1.5, "expectancy_r": 0.1}}
    rows = [_result_row("a", "paper_accept", sealed=sealed)]
    md = render_result(rows, "2026-06-21T00:00:00Z", {"4h": "abcd"})
    assert "PAPER CANDIDATE" in md
