"""Minute-level Binance Vision klines, stdlib only."""
from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class MinuteBar:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    quote_volume: float


def _normalize_ts_ms(ts: int) -> int:
    if ts >= 1_000_000_000_000_000:
        return ts // 1000
    return ts


def _parse_row(row: list[str]) -> MinuteBar | None:
    if len(row) < 8:
        return None
    try:
        return MinuteBar(
            ts_ms=_normalize_ts_ms(int(row[0].strip())),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            base_volume=float(row[5]),
            quote_volume=float(row[7]),
        )
    except (TypeError, ValueError):
        return None


def parse_vision_klines_csv(text: str) -> list[MinuteBar]:
    bars: list[MinuteBar] = []
    if not text.strip():
        return bars
    for row in csv.reader(io.StringIO(text)):
        bar = _parse_row(row)
        if bar is not None:
            bars.append(bar)
    return bars


def _cache_path(cache_dir: str, symbol: str, year: int, month: int) -> Path:
    return Path(cache_dir) / symbol / f"{year:04d}-{month:02d}.csv"


def _cache_marker_path(path: Path) -> Path:
    return Path(f"{path}.ok")


def _month_iter(start_ms: int, end_ms: int):
    if end_ms <= start_ms:
        return
    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    last = datetime.fromtimestamp((end_ms - 1) / 1000, tz=timezone.utc)
    year, month = start.year, start.month
    while (year, month) <= (last.year, last.month):
        yield year, month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1


def _read_cache(path: Path) -> str | None:
    if not path.exists() or not _cache_marker_path(path).exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_cache(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _cache_marker_path(path).write_text("ok", encoding="utf-8")


def _download_month(symbol: str, year: int, month: int) -> str | None:
    url = (
        "https://data.binance.vision/data/futures/um/monthly/klines/"
        f"{symbol}/1m/{symbol}-1m-{year:04d}-{month:02d}.zip"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            blob = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            names = archive.namelist()
            if not names:
                return None
            with archive.open(names[0]) as fh:
                return fh.read().decode("utf-8")
    except (zipfile.BadZipFile, UnicodeDecodeError, KeyError, OSError):
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError:
            return None


def fetch_vision_1m(
    symbol: str,
    start_ms: int,
    end_ms: int,
    cache_dir: str,
    download: Callable[[str, int, int], str | None] = _download_month,
) -> list[MinuteBar]:
    if end_ms <= start_ms:
        return []

    bars: list[MinuteBar] = []
    for year, month in _month_iter(start_ms, end_ms):
        path = _cache_path(cache_dir, symbol, year, month)
        text = _read_cache(path)
        if text is None:
            text = download(symbol, year, month)
            if text is None:
                text = ""
            _write_cache(path, text)
        bars.extend(parse_vision_klines_csv(text))

    deduped: dict[int, MinuteBar] = {}
    for bar in bars:
        deduped.setdefault(bar.ts_ms, bar)

    return [
        bar
        for ts, bar in sorted(deduped.items())
        if start_ms <= ts < end_ms
    ]
