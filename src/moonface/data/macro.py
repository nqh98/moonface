from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


@dataclass(frozen=True)
class MacroPoint:
    ts_ms: int
    value: float


def _midnight_ms(iso_day: str) -> int:
    d = date.fromisoformat(iso_day)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def parse_fred_csv(text: str) -> list[MacroPoint]:
    out: list[MacroPoint] = []
    for line in text.splitlines()[1:]:  # skip header
        line = line.strip()
        if not line or "," not in line:
            continue
        day, raw = line.split(",", 1)
        raw = raw.strip()
        if raw in ("", "."):  # FRED missing-value marker
            continue
        out.append(MacroPoint(ts_ms=_midnight_ms(day), value=float(raw)))
    out.sort(key=lambda p: p.ts_ms)
    return out


def _get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


def fetch_fred_series(series_id: str, cache_dir: str, get_text=_get_text) -> list[MacroPoint]:
    path = Path(cache_dir) / f"fred_{series_id}.csv"
    if path.exists():
        return parse_fred_csv(path.read_text())
    text = get_text(FRED_URL.format(series_id=series_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return parse_fred_csv(text)
