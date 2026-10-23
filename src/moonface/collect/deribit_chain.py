"""Deribit BTC options-chain snapshot collector (forward-collect lane).

Data acquisition ONLY: appends whole-chain snapshots to a durable CSV plus a
manifest, so the `newdata` readiness gate (>=180 days history, coverage >=0.95)
becomes reachable. No signal work, no alpha.
See experiments/newdata/FREE_DATA_FEASIBILITY_deribit_options.md (option A).

**Cadence is a parameter, and choosing it is a one-way door.** This collector
was daily-only until 2026-07-29. One snapshot per UTC day gives the gamma
*state* once a day and can never show the hedging *flow* within a day, so a
daily archive structurally cannot test an intraday dealer-hedging hypothesis —
and re-deciding the cadence after accrual starts resets the readiness clock.
Sub-daily data downsamples to daily; the reverse is impossible, so the default
is hourly. See docs/findings/COLLECTOR_AUDIT_2026-07-29.md.

Day-based stats (`days`, `history_days`, `coverage_ratio`) keep their exact
former meaning because `newdata.assess_manifest` gates on them; bucket stats
are additive.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CHAIN_URL = ("https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
             "?currency={cur}&kind=option")

_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
_EXPIRY_HOUR_UTC = 8  # Deribit options expire 08:00 UTC

HOUR_MS = 3_600_000
DAY_MS = 86_400_000
# Hourly by default: sub-daily downsamples to daily, daily cannot be upsampled.
# ~926 rows/snapshot x 24/day x 180 days is ~4M rows (~300 MB) — a full CSV scan
# per collection is a few seconds, which an hourly cadence tolerates.
DEFAULT_CADENCE_MS = HOUR_MS

CSV_FIELDS = ("ts_ms", "symbol", "expiry_ms", "strike", "option_type",
              "oi", "iv", "underlying_price")


@dataclass(frozen=True)
class ChainRow:
    ts_ms: int
    symbol: str
    expiry_ms: int
    strike: float
    option_type: str
    oi: float
    iv: float
    underlying_price: float


def parse_instrument_name(name: str) -> tuple[int, float, str]:
    """(expiry_ms, strike, option_type) from e.g. BTC-26DEC26-100000-C."""
    parts = name.split("-")
    if len(parts) != 4:
        raise ValueError(f"unparseable instrument name: {name}")
    _, expiry_s, strike_s, opt = parts
    if opt not in ("C", "P"):
        raise ValueError(f"unknown option type in: {name}")
    day = int(expiry_s[:-5])
    month = _MONTHS[expiry_s[-5:-2]]
    year = 2000 + int(expiry_s[-2:])
    expiry = dt.datetime(year, month, day, _EXPIRY_HOUR_UTC, tzinfo=dt.timezone.utc)
    strike = float(strike_s.replace("d", "."))
    return int(expiry.timestamp() * 1000), strike, opt


def parse_book_summary(payload: dict, ts_ms: int) -> tuple[list[ChainRow], int]:
    """All parseable chain rows stamped with the collector timestamp, plus a
    count of instruments skipped because their name failed to parse."""
    rows: list[ChainRow] = []
    skipped = 0
    for r in payload.get("result", []) or []:
        try:
            expiry_ms, strike, opt = parse_instrument_name(str(r["instrument_name"]))
            rows.append(ChainRow(
                ts_ms, str(r["instrument_name"]), expiry_ms, strike, opt,
                float(r.get("open_interest") or 0.0),
                float(r.get("mark_iv") or 0.0),
                float(r.get("underlying_price") or 0.0)))
        except (KeyError, ValueError, IndexError):
            skipped += 1
    rows.sort(key=lambda x: (x.expiry_ms, x.strike, x.option_type))
    return rows, skipped


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def csv_path(out_dir: str | Path, currency: str = "BTC") -> Path:
    return Path(out_dir) / f"chain_{currency}.csv"


def _utc_date(ts_ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).date()


def bucket_of(ts_ms: int, cadence_ms: int) -> int:
    """The cadence bucket a timestamp falls in — the collection unit."""
    return ts_ms // cadence_ms


def snapshot_stats(path: Path,
                   cadence_ms: int = DEFAULT_CADENCE_MS) -> dict:
    """Collection stats for the manifest, read from the durable CSV.

    `days` / `history_days` / `coverage_ratio` stay day-based because
    `newdata.assess_manifest` gates on them. `buckets` /
    `bucket_coverage_ratio` are additive and describe the actual cadence."""
    if not path.exists():
        return {"rows": 0, "days": 0, "history_days": 0, "coverage_ratio": 0.0,
                "buckets": 0, "bucket_coverage_ratio": 0.0,
                "monotonic_timestamps": True, "duplicate_timestamp_ratio": 0.0,
                "first_ts_ms": 0, "last_ts_ms": 0}
    ts_list: list[int] = []
    keys: set[tuple[int, str]] = set()
    dupes = 0
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            ts = int(row["ts_ms"])
            ts_list.append(ts)
            key = (ts, row["symbol"])
            if key in keys:
                dupes += 1
            keys.add(key)
    if not ts_list:
        return snapshot_stats(Path("/nonexistent"), cadence_ms)
    days = {_utc_date(t) for t in ts_list}
    span = (max(days) - min(days)).days + 1
    buckets = {bucket_of(t, cadence_ms) for t in ts_list}
    bucket_span = max(buckets) - min(buckets) + 1
    return {
        "rows": len(ts_list),
        "days": len(days),
        "history_days": span,
        "coverage_ratio": len(days) / span,
        "buckets": len(buckets),
        "bucket_coverage_ratio": len(buckets) / bucket_span,
        "monotonic_timestamps": all(a <= b for a, b in zip(ts_list, ts_list[1:])),
        "duplicate_timestamp_ratio": dupes / len(ts_list),
        "first_ts_ms": min(ts_list),
        "last_ts_ms": max(ts_list),
    }


def collected_dates(path: Path) -> set[dt.date]:
    if not path.exists():
        return set()
    with path.open(newline="") as fh:
        return {_utc_date(int(row["ts_ms"])) for row in csv.DictReader(fh)}


def collected_buckets(path: Path, cadence_ms: int) -> set[int]:
    """Cadence buckets already on disk — the idempotence key."""
    if not path.exists():
        return set()
    with path.open(newline="") as fh:
        return {bucket_of(int(row["ts_ms"]), cadence_ms)
                for row in csv.DictReader(fh)}


def append_snapshot(path: Path, rows: list[ChainRow]) -> int:
    """Append one snapshot; header is written on first touch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(CSV_FIELDS)
        for r in rows:
            w.writerow([r.ts_ms, r.symbol, r.expiry_ms, r.strike, r.option_type,
                        r.oi, r.iv, r.underlying_price])
    return len(rows)


def write_manifest(out_dir: Path, currency: str, stats: dict,
                   cadence_ms: int = DEFAULT_CADENCE_MS) -> Path:
    """Readiness-gate manifest (newdata.assess_manifest input), refreshed on
    every collection so the future gate pass is a pure read."""
    manifest = {
        "provider": "deribit",
        "data_class": "options_chain",
        "symbols": [currency],
        "fields": list(CSV_FIELDS),
        "cadence_ms": cadence_ms,
        "history_days": stats["history_days"],
        "coverage_ratio": stats["coverage_ratio"],
        "monotonic_timestamps": stats["monotonic_timestamps"],
        "duplicate_timestamp_ratio": stats["duplicate_timestamp_ratio"],
        # Deribit public API market data, keyless; same license stance already
        # accepted for the DVOL registration (feasibility doc Q4).
        "license": {"research_allowed": True, "derived_features_allowed": True,
                    "retention_allowed": True},
        "collection": {"rows": stats["rows"], "days": stats["days"],
                       "buckets": stats.get("buckets", 0),
                       "bucket_coverage_ratio":
                           stats.get("bucket_coverage_ratio", 0.0),
                       "first_ts_ms": stats["first_ts_ms"],
                       "last_ts_ms": stats["last_ts_ms"]},
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def collect_once(out_dir: str | Path, currency: str = "BTC",
                 now_ms: int | None = None, get_json=_get_json,
                 cadence_ms: int = DEFAULT_CADENCE_MS) -> dict:
    """Idempotent collection: at most one snapshot per cadence bucket.

    The network call happens only after the bucket check, so re-running inside
    a bucket costs nothing — that is what makes a once-a-minute cron safe."""
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000) \
        if now_ms is None else now_ms
    path = csv_path(out_dir, currency)
    today = _utc_date(now)
    if bucket_of(now, cadence_ms) in collected_buckets(path, cadence_ms):
        stats = snapshot_stats(path, cadence_ms)
        return {"status": "already_collected", "date": today.isoformat(),
                "appended": 0, "skipped": 0, "stats": stats}
    payload = get_json(CHAIN_URL.format(cur=currency))
    rows, skipped = parse_book_summary(payload, now)
    if not rows:
        return {"status": "empty_payload", "date": today.isoformat(),
                "appended": 0, "skipped": skipped,
                "stats": snapshot_stats(path, cadence_ms)}
    append_snapshot(path, rows)
    stats = snapshot_stats(path, cadence_ms)
    write_manifest(Path(out_dir), currency, stats, cadence_ms)
    return {"status": "collected", "date": today.isoformat(),
            "appended": len(rows), "skipped": skipped, "stats": stats}
