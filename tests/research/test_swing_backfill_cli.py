from moonface.research.universe_data import DailyRow
from tools.engine.swing_backfill import rank_symbols


def _row(ts, close, qvol):
    return DailyRow(ts_ms=ts, close=close, quote_volume=qvol)


def test_rank_symbols_orders_by_total_quote_volume_desc():
    rows = {
        "BTCUSDT": [_row(0, 100.0, 5000.0), _row(1, 100.0, 5000.0)],   # 10000
        "ETHUSDT": [_row(0, 50.0, 9000.0)],                             # 9000
        "SOLUSDT": [_row(0, 30.0, 20000.0)],                            # 20000
    }
    assert rank_symbols(rows, min_rows=1) == ["SOLUSDT", "BTCUSDT", "ETHUSDT"]


def test_rank_symbols_drops_symbols_below_min_history():
    rows = {"BTCUSDT": [_row(0, 100.0, 1.0)] * 400, "JUNKUSDT": [_row(0, 1.0, 1.0)] * 2}
    # require >= 365 daily rows
    assert rank_symbols(rows, min_rows=365) == ["BTCUSDT"]
