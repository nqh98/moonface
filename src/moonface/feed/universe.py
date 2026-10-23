"""Universe selection: top-N USDT-margined perps by 24h quote volume. Network
access only through the injected ``fetch_tickers`` seam (tests pass a fake)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ccxt


def _quote_volume(t: dict[str, Any]) -> float:
    info = t.get("info") or {}
    for key in ("quoteVolume", "quote_volume", "quoteVol"):
        raw = info.get(key)
        if raw not in (None, "", "0"):
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    raw = t.get("quoteVolume")
    try:
        return float(raw) if raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def select_top_volume(exchange_name: str, size: int,
                      *, fetch_tickers: Callable[[], dict[str, Any]] | None = None
                      ) -> list[str]:
    if fetch_tickers is None:
        exchange = getattr(ccxt, exchange_name)({"enableRateLimit": True})
        fetch_tickers = exchange.fetch_tickers
    tickers = fetch_tickers()
    perps = [(sym, _quote_volume(t)) for sym, t in tickers.items()
             if sym.endswith("/USDT:USDT")]
    perps = [(sym, v) for sym, v in perps if v > 0]
    perps.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in perps[:size]]
