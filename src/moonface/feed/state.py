"""Append-only open-setup store (jsonl). One open setup per symbol; resolves to
TP/SL/TIMEOUT against realized candles. Mirrors signal.journal's torn-line
handling and append-only contract."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from moonface.core.models import Candle
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup

_DEFAULT_MAX_BARS = 120   # ~20 days at 4h


def setup_hash(setup: Setup) -> str:
    raw = (f"{setup.setup_type}|{setup.side}|{setup.swept_level}"
           f"|{setup.struct_level}")
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _read(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            if idx == len(lines) - 1:          # tolerate a torn trailing write
                break
            raise ValueError(f"corrupt feed state line {idx + 1} in {p}")
    return out


def _append(path: str | Path, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def is_open(path: str | Path, symbol: str) -> bool:
    """One open setup per symbol. Append-only ledger: a symbol counts as open
    only when its MOST RECENT record is ``open`` — a later ``closed`` record
    settles it. (Records are never rewritten; resolve_open appends closes.)"""
    last: dict | None = None
    for r in _read(path):
        if r.get("symbol") == symbol:
            last = r
    return last is not None and last.get("status") == "open"


def open_setup(path: str | Path, symbol: str, setup: Setup,
               levels: Levels, candle_ts_ms: int) -> None:
    _append(path, {
        "symbol": symbol,
        "setup_hash": setup_hash(setup),
        "setup_type": setup.setup_type,
        "side": setup.side,
        "entry": levels.entry,
        "stop": levels.stop,
        "tp1": levels.tp1,
        "tp2": levels.tp2,
        "tp3": levels.tp3,
        "opened_candle_ts": candle_ts_ms,
        "status": "open",
    })


def resolve_open(path: str | Path, candles: list[Candle], tf_ms: int,
                 symbol: str | None = None,
                 max_bars: int = _DEFAULT_MAX_BARS) -> list[dict]:
    """Close open records against realized candles. Scans forward from each
    record's open candle; the first TP or SL hit wins, else TIMEOUT after
    ``max_bars``. If ``symbol`` is given, only that symbol's records are
    considered; records whose open candle is the last bar (no forward data yet)
    are left open for a later tick. Appends a `closed` record with outcome +
    realized_r (in R, signed) and returns the newly-closed records."""
    records = _read(path)
    by_ts = {c.timestamp_ms: i for i, c in enumerate(candles)}
    # Append-only idempotency: an open is settled once a later `closed` record
    # shares its (symbol, opened_candle_ts). Skip already-settled opens so the
    # repeating --watch tick doesn't append duplicate settlements.
    settled = {(r.get("symbol"), r.get("opened_candle_ts"))
               for r in records if r.get("status") == "closed"}
    closed: list[dict] = []
    for rec in records:
        if rec.get("status") != "open":
            continue
        if symbol is not None and rec.get("symbol") != symbol:
            continue
        if (rec.get("symbol"), rec.get("opened_candle_ts")) in settled:
            continue
        start = by_ts.get(rec["opened_candle_ts"])
        if start is None or start >= len(candles) - 1:
            continue                    # opened this tick — no forward bars yet
        long_ = rec["side"] == "LONG"
        entry, stop = rec["entry"], rec["stop"]
        tps = [rec["tp1"], rec["tp2"], rec["tp3"]]
        risk = (entry - stop) if long_ else (stop - entry)
        outcome, exit_price = "TIMEOUT", candles[min(start + max_bars,
                                                      len(candles) - 1)].close
        for j in range(start + 1, min(start + 1 + max_bars, len(candles))):
            c = candles[j]
            hit_sl = c.low <= stop if long_ else c.high >= stop
            hit_tp = any(c.high >= t for t in tps) if long_ else any(c.low <= t for t in tps)
            if hit_sl and (not hit_tp or _sl_first(c, stop, tps, long_)):
                outcome, exit_price = "SL", stop
                break
            if hit_tp:
                outcome, exit_price = "TP", _first_tp_hit(c, tps, long_)
                break
        realized = ((exit_price - entry) if long_ else (entry - exit_price))
        realized_r = round(realized / risk, 4) if risk > 0 else 0.0
        closed_rec = {**rec, "status": "closed", "outcome": outcome,
                      "realized_r": realized_r}
        _append(path, closed_rec)
        closed.append(closed_rec)
        settled.add((rec.get("symbol"), rec.get("opened_candle_ts")))
    return closed


def _sl_first(c: Candle, stop: float, tps: list[float], long_: bool) -> bool:
    """Did the candle plausibly hit the stop before a target? Conservative rule:
    if both the SL and a TP are within the same candle's range, assume SL first."""
    if long_:
        return c.low <= stop and any(t <= c.high for t in tps)
    return c.high >= stop and any(t >= c.low for t in tps)


def _first_tp_hit(c: Candle, tps: list[float], long_: bool) -> float:
    if long_:
        return min(t for t in tps if c.high >= t)
    return max(t for t in tps if c.low <= t)
