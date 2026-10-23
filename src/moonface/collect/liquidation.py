"""Binance USD-M liquidation-feed forward collector — pure core (Lane 3,
Track B / Setup 3 infrastructure).

Data acquisition ONLY. There is no free liquidation archive, so the sole path is
forward-collection off the live `!forceOrder@arr` WebSocket, which Binance
throttles to 1 order/sec/symbol (cascade magnitude is UNDERCOUNTED). This module
holds the pure parse/append/stats/manifest logic; the async WS shell lives in
tools/liquidation_collect.py. No trading, no alpha. Setup 3's pre-registration is
DEFERRED until the readiness gate in
experiments/newdata/FREE_DATA_FEASIBILITY_liquidations.md is met.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

CSV_FIELDS = ("ts_ms", "symbol", "side", "price", "qty", "notional")
CLUSTER_GAP_MS = 60_000  # liquidations within this gap = one cascade cluster


@dataclass(frozen=True)
class LiquidationRow:
    ts_ms: int
    symbol: str
    side: str
    price: float
    qty: float
    notional: float


def _row_from_order(o: dict, recv_ms: int) -> LiquidationRow | None:
    """A Binance forceOrder *order object* (the `o` payload) -> a normalized
    row, or None when a required field is missing or malformed."""
    try:
        symbol = str(o["s"])
        side = str(o["S"])
        qty = float(o["q"])
        price = float(o.get("ap") or o.get("p"))
        ts = int(o.get("T", recv_ms))
    except (KeyError, TypeError, ValueError):
        return None
    return LiquidationRow(ts, symbol, side, price, qty, qty * price)


def parse_force_order(payload: dict, recv_ms: int) -> LiquidationRow | None:
    """A full Binance forceOrder WS *envelope* -> a normalized row, or None if
    the message is not a parseable liquidation.

    NOTE the envelope/order distinction — it is the reason this collector
    silently wrote nothing for 16 days. The raw Binance frame is
    `{"e": "forceOrder", "o": {...}}`, but ccxt's unified liquidation hands
    back the INNER order object as `info`, which has no "e" key at all and
    whose own "o" key means order *type* ("LIMIT"), not a nested order. Feeding
    a ccxt `info` to this function therefore returns None for every message.
    Use `rows_from_liquidations`, which accepts both shapes."""
    if payload.get("e") != "forceOrder":
        return None
    return _row_from_order(payload.get("o") or {}, recv_ms)


def rows_from_liquidations(liqs: list, recv_ms: int,
                           symbol: str | None) -> list[LiquidationRow]:
    """Normalize one ccxt liquidation batch, keeping only `symbol` (None keeps
    everything). Unparseable entries are dropped, never raised — a malformed
    frame must not kill a collector that has to run for months.

    The collector subscribes to the all-market `!forceOrder@arr` firehose
    rather than a per-symbol channel: `<sym>@forceOrder` is too sparse to keep
    the websocket keepalive satisfied, so the socket was dropping on ping-pong
    timeout and reconnecting forever without ever receiving an event (16 days,
    zero rows — see experiments/COLLECTOR_AUDIT_2026-07-29.md). The firehose
    carries every symbol, so the declared scope is enforced here instead.

    Accepts BOTH payload shapes, because they are easy to confuse and getting
    it wrong is silent: a raw Binance envelope (`{"e": "forceOrder", "o": {}}`)
    and ccxt's unified `info`, which is the inner order object itself."""
    out: list[LiquidationRow] = []
    for liq in liqs:
        info = (liq or {}).get("info") or {}
        if info.get("e") == "forceOrder":
            row = parse_force_order(info, recv_ms)
        else:
            row = _row_from_order(info, recv_ms)
        if row is None:
            continue
        if symbol is not None and row.symbol != symbol:
            continue
        out.append(row)
    return out


def _utc_date(ts_ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).date()


def append_rows(path: Path, rows: list[LiquidationRow]) -> int:
    """Append rows; header is written on first touch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(CSV_FIELDS)
        for r in rows:
            w.writerow([r.ts_ms, r.symbol, r.side, r.price, r.qty, r.notional])
    return len(rows)


def snapshot_stats(path: Path) -> dict:
    """Collection stats for the manifest, read from the durable CSV."""
    if not path.exists():
        return {"rows": 0, "days": 0, "history_days": 0, "coverage_ratio": 0.0,
                "cascade_clusters": 0, "first_ts_ms": 0, "last_ts_ms": 0}
    ts_list: list[int] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            ts_list.append(int(row["ts_ms"]))
    if not ts_list:
        return snapshot_stats(Path("/nonexistent"))
    ts_sorted = sorted(ts_list)
    clusters = 1
    for a, b in zip(ts_sorted, ts_sorted[1:]):
        if b - a > CLUSTER_GAP_MS:
            clusters += 1
    days = {_utc_date(t) for t in ts_list}
    span = (max(days) - min(days)).days + 1
    return {
        "rows": len(ts_list),
        "days": len(days),
        "history_days": span,
        "coverage_ratio": len(days) / span,
        "cascade_clusters": clusters,
        "first_ts_ms": min(ts_list),
        "last_ts_ms": max(ts_list),
    }


def write_manifest(out_dir: Path, symbol: str, stats: dict) -> Path:
    """Readiness-gate manifest (newdata.assess_manifest input), refreshed on
    every collection so the future gate pass is a pure read."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "provider": "binance_usdm",
        "data_class": "liquidations",
        "symbols": [symbol],
        "fields": list(CSV_FIELDS),
        "throttle_note": "forceOrder WS throttled to 1 order/sec/symbol;"
                         " cascade magnitude is undercounted (sample, not tape)",
        "cadence": "event_stream",
        "history_days": stats["history_days"],
        "coverage_ratio": stats["coverage_ratio"],
        "cascade_clusters": stats["cascade_clusters"],
        "collection": {"rows": stats["rows"], "days": stats["days"],
                       "first_ts_ms": stats["first_ts_ms"],
                       "last_ts_ms": stats["last_ts_ms"]},
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path
