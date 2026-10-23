"""Consolidated runner: load shared data once, drive every adapter, collect rows."""
from __future__ import annotations

import types
from dataclasses import dataclass

from moonface.research.consolidated.adapters import ADAPTERS, EXCLUDED
from moonface.research.consolidated.result import metric_block
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles
from moonface.research.regime_overlay.data import load_macro
from tools.breadth.breadth import _load, _sha, SYMBOL, universe_covers_train


@dataclass
class RunContext:
    btc_4h: list
    btc_1h: list
    btc_2h: list
    funding: list  # RAW (ts, rate) points
    daily: dict
    is_member: object
    macro: dict
    start_ms: int
    end_ms: int
    cache_dir: str


def _build_context(start_ms: int, end_ms: int, cache_dir: str) -> RunContext:
    """Load all shared data once; separate so tests can monkeypatch it."""
    args = types.SimpleNamespace(start_ms=start_ms, end_ms=end_ms, cache_dir=cache_dir)
    btc_4h, daily, is_member = _load(args)
    btc_1h = fetch_perp_candles(SYMBOL, "1h", start_ms, end_ms, cache_dir)
    btc_2h = fetch_perp_candles(SYMBOL, "2h", start_ms, end_ms, cache_dir)
    funding = fetch_funding_rates(SYMBOL, start_ms, end_ms, cache_dir)
    macro = load_macro(cache_dir)
    train = btc_4h[: int(0.6 * len(btc_4h))]
    if not universe_covers_train(daily, is_member, train):
        raise RuntimeError(
            "universe daily history does not cover the train window "
            "(stale/short daily cache?)"
        )
    return RunContext(
        btc_4h=btc_4h,
        btc_1h=btc_1h,
        btc_2h=btc_2h,
        funding=funding,
        daily=daily,
        is_member=is_member,
        macro=macro,
        start_ms=start_ms,
        end_ms=end_ms,
        cache_dir=cache_dir,
    )


def run(start_ms: int, end_ms: int, cache_dir: str) -> dict:
    """Drive every adapter, collect rows + errors, sort by expectancy_r desc."""
    ctx = _build_context(start_ms, end_ms, cache_dir)
    rows: list[dict] = []
    errors: list[dict] = []

    for lane, fn in ADAPTERS.items():
        try:
            results = fn(ctx)
        except Exception as exc:  # noqa: BLE001
            row = {
                "key": None,
                "lane": lane,
                "config": None,
                "config_source": None,
                "exit_name": None,
                "current_signal": None,
                "status": "error",
                "error": str(exc),
                "expectancy_r": None,
                "pf": None,
                "max_dd_r": None,
                "n": None,
                "total_r": None,
                "mar": None,
            }
            rows.append(row)
            errors.append(row)
            continue
        for res in results:
            row = {
                "key": res.key,
                "lane": res.lane,
                "config": res.config,
                "config_source": res.config_source,
                "exit_name": res.exit_name,
                "current_signal": res.current_signal,
                "status": "ok",
            }
            row.update(metric_block(res))
            rows.append(row)

    # ok rows first (sorted by expectancy_r desc, tie n desc, total_r desc),
    # then error rows (expectancy_r is None → is None True sorts last).
    rows.sort(
        key=lambda r: (
            r.get("expectancy_r") is None,
            -(r.get("expectancy_r") or 0.0),
            -(r.get("n") or 0),
            -(r.get("total_r") or 0.0),
        )
    )

    btc_4h = getattr(ctx, "btc_4h", []) or []
    return {
        "rows": rows,
        "errors": errors,
        "excluded": list(EXCLUDED),
        "window": {"start_ms": start_ms, "end_ms": end_ms},
        "btc_bars": len(btc_4h),
        "btc_sha": _sha(btc_4h) if btc_4h else "",
    }
