"""Strict, stdlib-only loader for the frozen Binance Vision COIN-M pilot archives."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import io
from pathlib import Path
import re
from typing import Iterator
import zipfile

from moonface.research.forced_flow.iid_guard import Segment


ARCHIVE_WINDOW_START = datetime(2023, 6, 25, tzinfo=UTC)
ARCHIVE_WINDOW_END = datetime(2024, 10, 14, 23, tzinfo=UTC)

_KLINE_NAME = re.compile(r"BTCUSD_PERP-1h-\d{4}-\d{2}\.zip$")
_LIQUIDATION_NAME = re.compile(r"BTCUSD_PERP-liquidationSnapshot-\d{4}-\d{2}-\d{2}\.zip$")


class ArchiveError(ValueError):
    """The downloaded archive is not usable under the frozen pilot contract."""


@dataclass(frozen=True)
class ArchiveBars:
    timestamps: tuple[datetime, ...]
    closes: tuple[float, ...]
    liq_counts: tuple[int, ...]
    liq_imbalances: tuple[float, ...]
    segments: tuple[Segment, ...]


def load_coinm_bars(archive_root: Path) -> ArchiveBars:
    """Load exactly the frozen BTCUSD_PERP 1h window from Binance Vision ZIPs.

    Existing zero-row liquidation files are observed zero days. Absent liquidation
    files and missing kline hours are dropped; retained bars are split into ordered
    contiguous segments and never interpolated.
    """
    root = Path(archive_root)
    if not root.is_dir():
        raise ArchiveError(f"archive root does not exist: {root}")
    kline_rows = _load_klines(root)
    full_window = tuple(_hour_range(ARCHIVE_WINDOW_START, ARCHIVE_WINDOW_END))
    missing_klines = [timestamp for timestamp in full_window if timestamp not in kline_rows]
    if len(missing_klines) * 100 > len(full_window):
        raise ArchiveError("kline gaps exceed 1% of window bars")
    print_counts, buy_minus_sell, observed_liquidation_days = _load_liquidations(root)
    timestamps = tuple(
        timestamp
        for timestamp in full_window
        if timestamp in kline_rows and timestamp.date() in observed_liquidation_days
    )
    if not timestamps:
        raise ArchiveError("no retained bars after applying frozen archive gap rules")
    closes = tuple(kline_rows[timestamp] for timestamp in timestamps)
    liq_counts = tuple(print_counts.get(timestamp, 0) for timestamp in timestamps)
    liq_imbalances = tuple(
        buy_minus_sell.get(timestamp, 0) / max(print_counts.get(timestamp, 0), 1)
        for timestamp in timestamps
    )
    return ArchiveBars(timestamps, closes, liq_counts, liq_imbalances, _segments(timestamps))


def _load_klines(root: Path) -> dict[datetime, float]:
    rows_by_time: dict[datetime, tuple[tuple[str, ...], float]] = {}
    paths = _matching_archives(root, _KLINE_NAME)
    if not paths:
        raise ArchiveError("no BTCUSD_PERP 1h kline ZIPs found")
    for path in paths:
        for row_number, row in enumerate(_csv_rows(path)):
            if row_number == 0 and row[0].strip().lower() in {
                "open time",
                "open_time",
                "opentime",
            }:
                continue
            if len(row) < 12:
                raise ArchiveError(f"malformed kline row in {path.name}")
            milliseconds = _parse_milliseconds(row[0], "kline open time", path)
            if milliseconds % 3_600_000:
                raise ArchiveError(f"kline open time must be hour-aligned in {path.name}")
            timestamp = _utc_hour(milliseconds)
            try:
                close = float(row[4])
            except ValueError as error:
                raise ArchiveError(f"malformed kline close in {path.name}") from error
            if close <= 0:
                raise ArchiveError(f"kline close must be positive in {path.name}")
            if not ARCHIVE_WINDOW_START <= timestamp <= ARCHIVE_WINDOW_END:
                continue
            previous = rows_by_time.get(timestamp)
            raw = tuple(row)
            if previous is None:
                rows_by_time[timestamp] = (raw, close)
            elif previous[0] != raw:
                raise ArchiveError(f"conflicting kline rows for {timestamp.isoformat()}")
    return {timestamp: close for timestamp, (_, close) in rows_by_time.items()}


def _load_liquidations(
    root: Path,
) -> tuple[dict[datetime, int], dict[datetime, int], set[datetime.date]]:
    seen_rows: set[tuple[str, ...]] = set()
    print_counts: dict[datetime, int] = {}
    buy_minus_sell: dict[datetime, int] = {}
    observed_days: set[datetime.date] = set()
    for path in _matching_archives(root, _LIQUIDATION_NAME):
        archive_day = _liquidation_archive_day(path)
        if ARCHIVE_WINDOW_START.date() <= archive_day <= ARCHIVE_WINDOW_END.date():
            observed_days.add(archive_day)
        rows = _csv_rows(path)
        try:
            header = next(rows)
        except StopIteration as error:
            raise ArchiveError(f"empty liquidation ZIP: {path.name}") from error
        fields = {name.strip().lower(): index for index, name in enumerate(header)}
        if "time" not in fields or "side" not in fields:
            raise ArchiveError(f"liquidation header needs time and side in {path.name}")
        required_columns = max(fields["time"], fields["side"])
        for row in rows:
            if len(row) <= required_columns:
                raise ArchiveError(f"malformed liquidation row in {path.name}")
            raw = tuple(row)
            if raw in seen_rows:
                continue
            seen_rows.add(raw)
            timestamp = _utc_hour(
                _parse_milliseconds(row[fields["time"]], "liquidation time", path)
            )
            side = row[fields["side"]].strip().upper()
            if side not in {"BUY", "SELL"}:
                raise ArchiveError(f"malformed liquidation side in {path.name}: {side!r}")
            if not ARCHIVE_WINDOW_START <= timestamp <= ARCHIVE_WINDOW_END:
                continue
            print_counts[timestamp] = print_counts.get(timestamp, 0) + 1
            buy_minus_sell[timestamp] = buy_minus_sell.get(timestamp, 0) + (
                1 if side == "BUY" else -1
            )
    return print_counts, buy_minus_sell, observed_days


def _matching_archives(root: Path, pattern: re.Pattern[str]) -> list[Path]:
    return sorted(path for path in root.rglob("*.zip") if pattern.fullmatch(path.name))


def _csv_rows(path: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as archive:
        csv_members = [member for member in archive.namelist() if member.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ArchiveError(f"{path.name} must contain exactly one CSV member")
        with archive.open(csv_members[0]) as raw_file:
            with io.TextIOWrapper(raw_file, encoding="utf-8-sig", newline="") as text_file:
                for row in csv.reader(text_file):
                    if row:
                        yield row


def _parse_milliseconds(value: str, label: str, path: Path) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ArchiveError(f"malformed {label} in {path.name}") from error


def _utc_hour(milliseconds: int) -> datetime:
    timestamp = datetime.fromtimestamp(milliseconds / 1_000, tz=UTC)
    return timestamp.replace(minute=0, second=0, microsecond=0)


def _hour_range(start: datetime, end: datetime) -> Iterator[datetime]:
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def _liquidation_archive_day(path: Path) -> datetime.date:
    match = re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", path.name)
    if match is None:
        raise ArchiveError(f"invalid liquidation archive name: {path.name}")
    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


def _segments(timestamps: tuple[datetime, ...]) -> tuple[Segment, ...]:
    start = 0
    segments: list[Segment] = []
    starts_after_gap = timestamps[0] != ARCHIVE_WINDOW_START
    for index in range(1, len(timestamps)):
        if timestamps[index] != timestamps[index - 1] + timedelta(hours=1):
            segments.append(Segment(start, index, starts_after_gap=starts_after_gap))
            start = index
            starts_after_gap = True
    segments.append(Segment(start, len(timestamps), starts_after_gap=starts_after_gap))
    return tuple(segments)
