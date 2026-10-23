from __future__ import annotations

from moonface.core.models import Candle
from moonface.research.breadth.evaluate import (
    cell_entries,
    run_explore,
    score_records,
    summarize,
)
from moonface.research.breadth.grid import BreadthCell, EXIT_NAME, EXIT_PARAMS
from moonface.research.breadth.signals import DAY_MS
from moonface.research.universe_data import DailyRow

_H = 3_600_000


def _btc(n: int) -> list[Candle]:
    return [Candle(i * 4 * _H, 100 + i, 101 + i, 99 + i, 100 + i, 1.0)
            for i in range(n)]


def _cell(family: str = "pct_above_ma", axis: float = 2.0) -> BreadthCell:
    return BreadthCell(
        key=f"{family}:{axis:g}",
        family=family,
        axis=axis,
        long_thr=0.55,
        short_thr=0.45,
        low_band=0.40,
        high_band=0.60,
        base_period=2,
        h=48,
        exit_name=EXIT_NAME,
        exit_params=dict(EXIT_PARAMS),
    )


def _daily(closes: list[float]) -> dict[str, list[DailyRow]]:
    def rows(cs: list[float]) -> list[DailyRow]:
        return [DailyRow(i * DAY_MS, c, 1.0) for i, c in enumerate(cs)]

    return {"AAA": rows(closes), "BBB": rows(closes)}


def test_score_records_and_summarize_split_sides() -> None:
    btc = _btc(60)
    recs = score_records(btc, [(10, "LONG"), (20, "SHORT")], EXIT_NAME, EXIT_PARAMS)
    m = summarize(recs)
    assert m["trade_count"] == len(recs)
    assert m["long_trade_count"] + m["short_trade_count"] == m["trade_count"]


def test_cell_entries_long_on_broad_uptrend() -> None:
    daily = _daily([10, 11, 12, 13, 14, 15])
    btc = _btc(60)
    entries = cell_entries(daily, btc, _cell(axis=2.0))
    assert entries and all(side == "LONG" for _, side in entries)


def test_run_explore_adds_dsr_and_sorts() -> None:
    daily = _daily([10, 11, 12, 13, 14, 15])
    btc = _btc(80)
    cells = [_cell(axis=2.0), _cell(family="breadth_momentum", axis=1.0)]
    rows = run_explore(daily, btc, cells)
    assert all("dsr" in r and 0.0 <= r["dsr"] <= 1.0 for r in rows)
    totals = [r["metrics"]["total_r"] for r in rows]
    assert totals == sorted(totals, reverse=True)
