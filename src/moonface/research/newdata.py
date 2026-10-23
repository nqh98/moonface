from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_CLASSES = ("l2_orderbook", "aggressor_trades", "account_positioning",
                "macro_series", "implied_vol", "options_chain")

REQUIRED_FIELDS = {
    "l2_orderbook": ("ts_ms", "symbol", "bid_prices", "bid_sizes", "ask_prices", "ask_sizes"),
    "aggressor_trades": ("ts_ms", "symbol", "side", "price", "size"),
    "account_positioning": ("ts_ms", "symbol", "long_ratio", "short_ratio"),
    "macro_series": ("ts_ms", "series_id", "value", "publish_lag_days"),
    "implied_vol": ("ts_ms", "symbol", "dvol_open", "dvol_high", "dvol_low", "dvol_close"),
    "options_chain": ("ts_ms", "symbol", "expiry_ms", "strike", "option_type",
                      "oi", "iv", "underlying_price"),
}

# macro_series is an exogenous (non-crypto) feed; it does not require a crypto symbol.
_BTC_REQUIRED = {"l2_orderbook", "aggressor_trades", "account_positioning", "implied_vol"}
# options_chain is keyed by the Deribit underlying currency, not the perp symbol.
_CURRENCY_REQUIRED = {"options_chain": "BTC"}

MIN_HISTORY_DAYS = 180
MIN_COVERAGE_RATIO = 0.95
MAX_DUPLICATE_TS_RATIO = 0.01


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def assess_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    data_class = str(manifest.get("data_class", ""))
    fields = set(manifest.get("fields", []))
    symbols = set(manifest.get("symbols", []))
    license_info = manifest.get("license", {})

    if data_class not in DATA_CLASSES:
        failures.append("data_class must be one of the frozen new-data classes")
    else:
        missing = [f for f in REQUIRED_FIELDS[data_class] if f not in fields]
        if missing:
            failures.append(f"missing required fields: {', '.join(missing)}")

    if data_class in _BTC_REQUIRED and "BTCUSDT" not in symbols:
        failures.append("BTCUSDT coverage is required")
    required_currency = _CURRENCY_REQUIRED.get(data_class)
    if required_currency and required_currency not in symbols:
        failures.append(f"{required_currency} coverage is required")
    if int(manifest.get("history_days", 0)) < MIN_HISTORY_DAYS:
        failures.append("history_days must be at least 180")
    if float(manifest.get("coverage_ratio", 0.0)) < MIN_COVERAGE_RATIO:
        failures.append("coverage_ratio must be at least 0.95")
    if not bool(manifest.get("monotonic_timestamps", False)):
        failures.append("timestamps must be monotonic")
    if float(manifest.get("duplicate_timestamp_ratio", 1.0)) > MAX_DUPLICATE_TS_RATIO:
        failures.append("duplicate_timestamp_ratio must be <= 0.01")
    if not bool(license_info.get("research_allowed", False)):
        failures.append("research use must be licensed")
    if not bool(license_info.get("derived_features_allowed", False)):
        failures.append("derived feature retention/use must be licensed")
    if not bool(license_info.get("retention_allowed", False)):
        failures.append("sample/data retention must be licensed")

    return {
        "status": "ready" if not failures else "blocked",
        "provider": manifest.get("provider", ""),
        "data_class": data_class,
        "failures": failures,
        "checks": {
            "symbols": sorted(symbols),
            "history_days": int(manifest.get("history_days", 0)),
            "cadence_ms": int(manifest.get("cadence_ms", 0)),
            "coverage_ratio": float(manifest.get("coverage_ratio", 0.0)),
            "monotonic_timestamps": bool(manifest.get("monotonic_timestamps", False)),
            "duplicate_timestamp_ratio": float(manifest.get("duplicate_timestamp_ratio", 1.0)),
            "fields": sorted(fields),
        },
    }


def render_candidates() -> str:
    payload = {
        "data_classes": list(DATA_CLASSES),
        "required_fields": REQUIRED_FIELDS,
        "gate": {
            "min_history_days": MIN_HISTORY_DAYS,
            "min_coverage_ratio": MIN_COVERAGE_RATIO,
            "max_duplicate_timestamp_ratio": MAX_DUPLICATE_TS_RATIO,
            "required_symbol": "BTCUSDT",
        },
        "excluded": ["ohlcv", "funding", "basis", "open_interest", "calendar"],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_report(verdict: dict[str, Any]) -> str:
    lines = [
        "# New-data readiness verdict",
        "",
        f"- status: {verdict['status']}",
        f"- provider: {verdict['provider']}",
        f"- data class: {verdict['data_class']}",
        "",
        "No signal tests, return tests, or strategy backtests were run.",
        "",
        "## Gate Failures",
    ]
    failures = verdict.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- none")
    lines.extend(["", "## Checks", "", "```json", json.dumps(verdict["checks"], indent=2), "```"])
    return "\n".join(lines) + "\n"
