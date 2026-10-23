from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.data.ohlcv import OhlcvCache
from moonface.config import Settings
from moonface.core.models import Candle

import pytest

pytestmark = pytest.mark.slow


def _trending_h1(n: int) -> list[Candle]:
    out = []
    price = 100.0
    for i in range(n):
        price += 0.5
        out.append(Candle(1780275600000 + i * 3_600_000, price, price + 3,
                          price - 3, price + 1, 10.0))
    return out


class ProbeCliTest(unittest.TestCase):
    def test_generates_leaderboard_from_cached_data(self) -> None:
        from tools.probe import run_probe

        with TemporaryDirectory() as d:
            cache_dir = Path(d) / "cache"
            cache = OhlcvCache(str(cache_dir))
            candles = _trending_h1(600)
            for tf in ("1h", "4h", "1d", "1w"):
                cache.save("BTC/USDT", tf, candles)

            out = run_probe(
                exchange="binance", symbol="BTC/USDT",
                start_ms=candles[0].timestamp_ms, end_ms=candles[-1].timestamp_ms + 1,
                cache_dir=str(cache_dir), settings=Settings.from_env(),
                fee_rate=0.0, slippage=0.0, k=1.0, m=2.0, n_bars=12,
                atr_period=14, oos_tail_bars=120, warmup=60, future_bars=12,
                out_root=Path(d) / "out",
            )
            self.assertTrue((out / "leaderboard.md").exists())
            self.assertTrue((out / "leaderboard.json").exists())


class LeaderboardColumnsTest(unittest.TestCase):
    def test_markdown_includes_oos_horizon_columns(self) -> None:
        from tools.probe import _render_markdown
        from moonface.research.edge.score import ProbeRow
        row = ProbeRow(
            signal="x", params={}, bracket_trades=1, bracket_net_r=0.0,
            bracket_expectancy_r=0.0, bracket_win_rate=0.0, bracket_valid=False,
            bracket_oos_net_r=0.0, bracket_oos_trades=0, horizon_trades=1,
            horizon_expectancy_r=0.1, horizon_win_rate=0.5,
            horizon_oos_expectancy_r=0.2, horizon_oos_trades=3,
        )
        md = _render_markdown([row])
        self.assertIn("hzn OOS exp", md)
        self.assertIn("hzn OOS n", md)
        self.assertIn("0.2", md)


class TimeframeHeaderTest(unittest.TestCase):
    def test_markdown_header_includes_timeframe(self) -> None:
        from tools.probe import _render_markdown
        md = _render_markdown([], "4h")
        self.assertIn("- timeframe: 4h", md)
