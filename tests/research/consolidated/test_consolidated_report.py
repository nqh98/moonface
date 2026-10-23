"""Tests for consolidated leaderboard report."""

from __future__ import annotations

from moonface.research.consolidated.report import render_markdown, render_json


def test_report_has_banner_and_evidence_class():
    result = {
        "rows": [
            {
                "rank": 1,
                "lane": "x",
                "key": "x:1",
                "expectancy_r": 0.1,
                "pf": 1.2,
                "max_dd_r": -3.0,
                "n": 20,
                "total_r": 2.0,
                "mar": 0.5,
                "current_signal": "LONG",
                "config_source": "frozen_family",
                "exit_name": "atr_trail",
            },
        ],
        "excluded": [{"lane": "portfolio", "reason": "bar-return"}],
        "errors": [],
        "window": {"start_ms": 1, "end_ms": 2},
        "btc_bars": 10,
        "btc_sha": "abc",
    }
    md = render_markdown(result, "2026-06-29")
    assert "DIAGNOSTIC RE-RANK" in md and "portfolio" in md
    assert "atr_trail" in md
    js = render_json(result, "2026-06-29")
    assert js["evidence_class"] == "diagnostic_rerank"
    assert js["sealed_holdouts"] == "conceptually_reopened"


def test_errors_section_only_when_nonempty():
    result = {
        "rows": [],
        "excluded": [],
        "errors": [{"lane": "bad", "error": "boom"}],
        "window": {"start_ms": 0, "end_ms": 1},
        "btc_bars": 5,
        "btc_sha": "x",
    }
    md = render_markdown(result, "2026-06-29")
    assert "## Errors" in md
    assert "boom" in md


def test_no_errors_section_when_empty():
    result = {
        "rows": [],
        "excluded": [],
        "errors": [],
        "window": {"start_ms": 0, "end_ms": 1},
        "btc_bars": 5,
        "btc_sha": "x",
    }
    md = render_markdown(result, "2026-06-29")
    assert "## Errors" not in md


def test_banner_is_first_line():
    result = {"rows": [], "excluded": [], "errors": [], "window": {}, "btc_bars": 0, "btc_sha": ""}
    md = render_markdown(result, "2026-06-29")
    assert md.startswith("> **DIAGNOSTIC RE-RANK")


def test_non_ok_rows_skipped():
    result = {
        "rows": [
            {"rank": 1, "status": "error", "lane": "a", "key": "a:1", "expectancy_r": 0, "pf": 1, "max_dd_r": -1, "n": 1, "total_r": 0, "mar": 0, "current_signal": "", "config_source": "", "exit_name": ""},
            {"rank": 2, "status": "ok", "lane": "b", "key": "b:1", "expectancy_r": 0.5, "pf": 1.5, "max_dd_r": -2, "n": 10, "total_r": 5, "mar": 1, "current_signal": "SHORT", "config_source": "frozen", "exit_name": "fixed"},
        ],
        "excluded": [],
        "errors": [],
        "window": {},
        "btc_bars": 0,
        "btc_sha": "",
    }
    md = render_markdown(result, "2026-06-29")
    # the error row is skipped from the ranked table; only the ok row appears
    assert "b:1" in md
    assert "a:1" not in md


def test_render_json_keys():
    result = {"rows": [], "excluded": [], "errors": [], "window": {}, "btc_bars": 0, "btc_sha": ""}
    js = render_json(result, "2026-06-29")
    expected_keys = {"evidence_class", "sealed_holdouts", "asof", "window", "btc_bars", "btc_sha", "rows", "excluded", "errors"}
    assert set(js.keys()) == expected_keys
    assert js["asof"] == "2026-06-29"
