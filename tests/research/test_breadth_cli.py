from __future__ import annotations

from pathlib import Path

from moonface.core.models import Candle
import tools.breadth.breadth as cli


def _c(n: int) -> list[Candle]:
    return [Candle(i, 100.0, 101.0, 99.0, 100.0, 1.0) for i in range(n)]


def test_split_60_20_20() -> None:
    tr, va, se = cli.split_60_20_20(_c(100))
    assert (len(tr), len(va), len(se)) == (60, 20, 20)


def test_membership_fn_static_window(tmp_path: Path) -> None:
    from moonface.research.universe_data import DailyRow

    daily = {
        "AAA": [DailyRow(i * cli.DAY_MS, 10 + i, 100.0) for i in range(400)],
        "BBB": [DailyRow(i * cli.DAY_MS, 10 + i, 50.0) for i in range(400)],
    }
    is_member = cli.membership_fn(
        daily,
        top_n=1,
        min_history_days=30,
        vol_days=30,
        rebalance_days=30,
    )
    late = 390 * cli.DAY_MS
    assert is_member("AAA", late) is True
    assert is_member("BBB", late) is False


def test_universe_covers_train_guard() -> None:
    from moonface.research.universe_data import DailyRow

    # daily history spans days 0..399; build a member predicate that admits both.
    daily = {
        "AAA": [DailyRow(i * cli.DAY_MS, 10 + (i % 5), 100.0) for i in range(400)],
        "BBB": [DailyRow(i * cli.DAY_MS, 10 + (i % 7), 50.0) for i in range(400)],
    }
    always = lambda sym, ts: True  # noqa: E731 - terse test predicate
    # period-50 breadth series spans daily ts 49..399; train bars at days 60..109
    # fall inside it -> covered.
    covered = [Candle((60 + i) * cli.DAY_MS, 100.0, 101.0, 99.0, 100.0, 1.0)
               for i in range(50)]
    assert cli.universe_covers_train(daily, always, covered, min_points=10) is True

    # train bars far in the future, beyond all daily history -> NOT covered
    far = [Candle((900 + i) * cli.DAY_MS, 100.0, 101.0, 99.0, 100.0, 1.0)
           for i in range(50)]
    assert cli.universe_covers_train(daily, always, far, min_points=10) is False
