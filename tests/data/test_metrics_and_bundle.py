# tests/test_metrics_data.py
import pytest

from moonface.data.series import (METRICS_FIELDS, align_metric,
                                            fetch_metrics_history,
                                            parse_metrics_csv)
from moonface.core.models import Candle

_H4_MS = 4 * 3_600_000
_DAY_MS = 86_400_000

_CSV = (
    "create_time,symbol,sum_open_interest,sum_open_interest_value,"
    "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
    "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
    "2026-06-09 00:05:00,BTCUSDT,98517.828,6207086197.79,1.957,1.180,1.832,0.892\n"
    "2026-06-09 00:10:00,BTCUSDT,98501.192,6205575096.00,1.956,1.180,1.831,1.195\n"
)


def test_parse_metrics_csv_returns_utc_ms_rows():
    rows = parse_metrics_csv(_CSV)
    assert len(rows) == 2
    ts, fields = rows[0]
    assert ts == 1780963500000  # 2026-06-09 00:05:00 UTC
    assert fields["sum_open_interest"] == pytest.approx(98517.828)
    assert fields["sum_taker_long_short_vol_ratio"] == pytest.approx(0.892)
    assert set(fields) == METRICS_FIELDS


def _candles(start_ms, n):
    return [Candle(start_ms + i * _H4_MS, 1.0, 1.0, 1.0, 1.0, 1.0)
            for i in range(n)]


def test_align_metric_is_as_of_join_on_open_time():
    candles = _candles(1_000_000_000_000, 3)
    points = [
        (1_000_000_000_000 - 1, 10.0),        # before bar 0 opens
        (1_000_000_000_000 + _H4_MS, 20.0),   # exactly at bar 1 open
        (1_000_000_000_000 + 2 * _H4_MS + 1, 30.0),  # after bar 2 opens
    ]
    assert align_metric(candles, points) == [10.0, 20.0, 20.0]


def test_align_metric_before_first_point_is_none():
    candles = _candles(1_000_000_000_000, 2)
    points = [(1_000_000_000_000 + _H4_MS, 5.0)]
    assert align_metric(candles, points) == [None, 5.0]


def _fake_day_csv(day_ms):
    """One synthetic 5-min row at 00:05 of the given UTC day."""
    import datetime as dt
    t = dt.datetime.fromtimestamp(day_ms / 1000, dt.timezone.utc)
    stamp = t.strftime("%Y-%m-%d") + " 00:05:00"
    return (
        "create_time,symbol,sum_open_interest,sum_open_interest_value,"
        "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
        "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
        f"{stamp},BTCUSDT,1.0,1.0,1.0,1.0,1.0,1.0\n")


def test_fetch_downloads_missing_days_then_serves_from_cache(tmp_path,
                                                             monkeypatch):
    import moonface.data.series as md
    calls = []

    def fake_download(symbol, day_ms):
        calls.append(day_ms)
        return _fake_day_csv(day_ms)

    monkeypatch.setattr(md, "_download_day", fake_download)
    day0 = 1_700_006_400_000 - (1_700_006_400_000 % _DAY_MS)
    rows = fetch_metrics_history("BTCUSDT", day0, day0 + 2 * _DAY_MS,
                                 str(tmp_path))
    assert len(rows) == 3  # one synthetic row per day, 3 days touched
    assert len(calls) == 3
    # second fetch: fully cached, no downloads
    rows2 = fetch_metrics_history("BTCUSDT", day0, day0 + 2 * _DAY_MS,
                                  str(tmp_path))
    assert rows2 == rows
    assert len(calls) == 3


def test_fetch_skips_days_missing_from_archive(tmp_path, monkeypatch):
    import moonface.data.series as md
    day0 = 1_700_006_400_000 - (1_700_006_400_000 % _DAY_MS)

    def fake_download(symbol, day_ms):
        return None if day_ms == day0 + _DAY_MS else _fake_day_csv(day_ms)

    monkeypatch.setattr(md, "_download_day", fake_download)
    rows = fetch_metrics_history("BTCUSDT", day0, day0 + 2 * _DAY_MS,
                                 str(tmp_path))
    assert len(rows) == 2  # the 404 day is simply absent
    assert all(ts // _DAY_MS != (day0 + _DAY_MS) // _DAY_MS for ts, _ in rows)


def test_load_bundle_attaches_metrics_feature(tmp_path, monkeypatch):
    import moonface.data.bundle as bundle_mod
    candles = _candles(1_700_006_400_000, 100)

    monkeypatch.setattr(bundle_mod, "fetch_history",
                        lambda *a, **kw: candles)
    monkeypatch.setattr(
        bundle_mod, "fetch_metrics_history",
        lambda symbol, s, e, cache_dir: [(c.timestamp_ms, {
            f: 2.5 for f in METRICS_FIELDS}) for c in candles])
    asset = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
             "timeframe": "4h", "metrics_field": "sum_open_interest"}
    b = bundle_mod.load_bundle(asset, candles[0].timestamp_ms,
                               candles[-1].timestamp_ms + _H4_MS,
                               str(tmp_path))
    assert b.feature is not None and len(b.feature) == 100
    assert b.feature[-1] == 2.5


def test_load_bundle_rejects_thin_metrics_coverage(tmp_path, monkeypatch):
    import moonface.data.bundle as bundle_mod
    candles = _candles(1_700_006_400_000, 100)
    monkeypatch.setattr(bundle_mod, "fetch_history",
                        lambda *a, **kw: candles)
    monkeypatch.setattr(
        bundle_mod, "fetch_metrics_history",
        lambda symbol, s, e, cache_dir: [(candles[-1].timestamp_ms,
                                          {f: 1.0 for f in METRICS_FIELDS})])
    asset = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
             "timeframe": "4h", "metrics_field": "sum_open_interest"}
    with pytest.raises(ValueError, match="coverage"):
        bundle_mod.load_bundle(asset, candles[0].timestamp_ms,
                               candles[-1].timestamp_ms + _H4_MS,
                               str(tmp_path))


def test_parse_metrics_csv_omits_empty_fields():
    csv_text = (
        "create_time,symbol,sum_open_interest,sum_open_interest_value,"
        "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
        "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
        "2023-06-15 00:05:00,BTCUSDT,1.0,,1.0,,1.0,1.0\n")
    rows = parse_metrics_csv(csv_text)
    assert len(rows) == 1
    _ts, fields = rows[0]
    assert "sum_open_interest_value" not in fields
    assert "sum_toptrader_long_short_ratio" not in fields
    assert fields["sum_open_interest"] == 1.0


def test_fetch_flushes_cache_incrementally(tmp_path, monkeypatch):
    import moonface.data.series as md
    day0 = 1_700_006_400_000 - (1_700_006_400_000 % _DAY_MS)
    boom_at = day0 + 150 * _DAY_MS

    def fake_download(symbol, day_ms):
        if day_ms >= boom_at:
            raise RuntimeError("network died mid-backfill")
        return _fake_day_csv(day_ms)

    monkeypatch.setattr(md, "_download_day", fake_download)
    with pytest.raises(RuntimeError):
        fetch_metrics_history("BTCUSDT", day0, day0 + 200 * _DAY_MS,
                              str(tmp_path))
    # the first flushed batch survives the crash
    import moonface.data.series as md2
    cached = md2._read_cache(md2._cache_path(str(tmp_path), "BTCUSDT"))
    assert len(cached) >= 100


def test_load_bundle_skips_rows_missing_the_field(tmp_path, monkeypatch):
    import moonface.data.bundle as bundle_mod
    candles = _candles(1_700_006_400_000, 100)
    monkeypatch.setattr(bundle_mod, "fetch_history", lambda *a, **kw: candles)

    def fake_metrics(symbol, s, e, cache_dir):
        rows = []
        for i, c in enumerate(candles):
            fields = {f: 2.5 for f in METRICS_FIELDS}
            if i % 10 == 0:
                del fields["sum_open_interest"]   # sparse field
            rows.append((c.timestamp_ms, fields))
        return rows

    monkeypatch.setattr(bundle_mod, "fetch_metrics_history", fake_metrics)
    asset = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
             "timeframe": "4h", "metrics_field": "sum_open_interest"}
    b = bundle_mod.load_bundle(asset, candles[0].timestamp_ms,
                               candles[-1].timestamp_ms + _H4_MS,
                               str(tmp_path))
    # as-of join carries the previous value across the sparse rows
    assert b.feature[1] == 2.5 and b.feature[10] == 2.5


def test_cache_roundtrips_sparse_rows(tmp_path):
    from moonface.data.series import _cache_path, _read_cache, _write_cache
    full = {f: 1.5 for f in METRICS_FIELDS}
    sparse = {f: 2.5 for f in METRICS_FIELDS if f != "sum_open_interest"}
    rows = [(1_000, full), (2_000, sparse)]
    path = _cache_path(str(tmp_path), "BTCUSDT")
    _write_cache(path, rows)
    assert _read_cache(path) == rows
