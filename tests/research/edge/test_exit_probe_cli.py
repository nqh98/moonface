# tests/test_exit_probe_cli.py
from __future__ import annotations

import unittest

from moonface.research.edge.exit_score import ExitRow
from tools.lanes.exit_probe import _render_markdown


class LeaderboardTest(unittest.TestCase):
    def test_markdown_includes_columns_and_values(self) -> None:
        row = ExitRow(
            entry="atr_channel_break", entry_params={"k": 2.0}, exit="atr_trail",
            exit_params={"k_trail": 2.0}, research_trades=100, research_net_r=12.0,
            research_expectancy_r=0.12, research_max_dd_r=-4.0, oos_trades=40,
            oos_net_r=6.0, oos_expectancy_r=0.15, valid=True)
        md = _render_markdown([row])
        self.assertIn("| entry | exit |", md)
        self.assertIn("OOS exp", md)
        self.assertIn("valid", md)
        self.assertIn("atr_trail", md)
        self.assertIn("0.15", md)


class TimeframeHeaderTest(unittest.TestCase):
    def test_markdown_header_includes_timeframe(self) -> None:
        self.assertIn("- timeframe: 4h", _render_markdown([], "4h"))