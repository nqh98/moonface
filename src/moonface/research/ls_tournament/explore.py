"""Long/short evaluator for the BTC practical tournament grid."""
from __future__ import annotations

from moonface.core.metrics import (_kurtosis, _sharpe, _skew,
                                         deflated_sharpe, summarize_r,
                                         single_trade_r)
from moonface.data.series import align_funding, align_metric
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap
from moonface.research.ls_tournament.grid import ExploreConfig

# Timestamp-keyed external series. They are aligned to candles by timestamp
# (as-of, no-lookahead) inside each filter, so they must NOT be index-sliced
# when a sub-window is taken; align_* re-derives the per-candle view.
_TIMESTAMP_KEYED = ("funding", "macro", "oi_points")


def _context_value(context, key: str):
    if context is None:
        return None
    if hasattr(context, key):
        return getattr(context, key)
    if hasattr(context, "get"):
        return context.get(key)
    return None


def _slice_context(context, start: int | None = None, end: int | None = None):
    if context is None:
        return None
    if hasattr(context, "candles") and hasattr(context, "funding"):
        kwargs = {
            "candles": context.candles[slice(start, end)],
            "funding": None if context.funding is None else context.funding[slice(start, end)],
            "basis": None if getattr(context, "basis", None) is None else context.basis[slice(start, end)],
            "feature": None if getattr(context, "feature", None) is None else context.feature[slice(start, end)],
            "bookdepth": None if getattr(context, "bookdepth", None) is None else context.bookdepth[slice(start, end)],
        }
        return type(context)(**kwargs)
    if not hasattr(context, "items"):
        return context
    out = {}
    for key, value in context.items():
        if key in _TIMESTAMP_KEYED:
            out[key] = value  # aligned by timestamp inside filters; never index-sliced
        elif isinstance(value, list):
            out[key] = value[slice(start, end)]
        elif isinstance(value, dict):
            out[key] = {
                sub_key: (sub_val[slice(start, end)] if isinstance(sub_val, list) else sub_val)
                for sub_key, sub_val in value.items()
            }
        else:
            out[key] = value
    return out


def _series_at(series, idx: int):
    if series is None or idx >= len(series):
        return None
    return series[idx]


def _rule_entries(candles, rule: dict, side: str) -> list[tuple[int, str]]:
    gen = PRICE_FAMILIES[rule["family"]]
    entries = gen(candles, rule["params"])
    return [(i, s) for i, s in entries if s == side]


def _sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def _atr_series(candles, period: int) -> list[float]:
    from moonface.core.risk import atr

    out: list[float] = []
    for i in range(len(candles)):
        out.append(atr(candles[: i + 1], period))
    return out


def _apply_slow_ma_regime(candles, entries, params: dict) -> list[tuple[int, str]]:
    period = int(params["period"])
    closes = [c.close for c in candles]
    kept: list[tuple[int, str]] = []
    for i, side in entries:
        ma = _sma(closes[: i + 1], period)
        if ma is None:
            continue
        close = candles[i].close
        if side == "LONG" and close > ma:
            kept.append((i, side))
        elif side == "SHORT" and close < ma:
            kept.append((i, side))
    return kept


def _apply_atr_band(candles, entries, params: dict) -> list[tuple[int, str]]:
    window = int(params["window"])
    low = float(params["low"])
    high = float(params["high"])
    atr_period = int(params["atr_period"])
    atrs = _atr_series(candles, atr_period)
    kept: list[tuple[int, str]] = []
    for i, side in entries:
        if i + 1 < window:
            continue
        sample = [a for a in atrs[i + 1 - window:i + 1] if a > 0]
        cur = atrs[i]
        if not sample or cur <= 0:
            continue
        rank = sum(1 for a in sample if a <= cur) / len(sample)
        if low <= rank <= high:
            kept.append((i, side))
    return kept


def _apply_funding_extreme(candles, entries, context, params: dict) -> list[tuple[int, str]]:
    points = _context_value(context, "funding")
    if not points:
        return list(entries)
    funding = align_funding(candles, points)  # (ts, rate) pairs -> per-candle, no lookahead
    thr = float(params["thr"])
    kept: list[tuple[int, str]] = []
    for i, side in entries:
        value = _series_at(funding, i)
        if value is None:
            continue
        if side == "LONG" and value <= -thr:
            kept.append((i, side))
        elif side == "SHORT" and value >= thr:
            kept.append((i, side))
    return kept


def _apply_oi_momentum(candles, entries, context, params: dict) -> list[tuple[int, str]]:
    points = _context_value(context, "oi_points")
    if not points:
        return list(entries)
    oi = align_metric(candles, points)  # (ts, open_interest) -> per-candle, no lookahead
    window = int(params["window"])
    lookback = int(params["lookback"])
    z_thr = float(params["z_thr"])
    kept: list[tuple[int, str]] = []
    for i, side in entries:
        if i < window + lookback:
            continue
        now = _series_at(oi, i)
        then = _series_at(oi, i - lookback)
        if now is None or then in (None, 0):
            continue
        recent = []
        for j in range(i + 1 - window, i + 1):
            cur = _series_at(oi, j)
            prev = _series_at(oi, j - lookback)
            if cur is not None and prev not in (None, 0):
                recent.append(cur / prev - 1.0)
        if len(recent) < window // 2:
            continue
        mean = sum(recent) / len(recent)
        var = sum((x - mean) ** 2 for x in recent) / len(recent)
        if var <= 0:
            continue
        z = ((now / then) - 1.0 - mean) / (var ** 0.5)
        if side == "LONG" and z >= z_thr:
            kept.append((i, side))
        elif side == "SHORT" and z <= -z_thr:
            kept.append((i, side))
    return kept


def _apply_macro_regime(candles, entries, context, params: dict) -> list[tuple[int, str]]:
    macro = _context_value(context, "macro")
    if macro is None:
        macro = _context_value(context, "fred")
    if macro is None:
        return list(entries)
    from moonface.research.regime_overlay.regime import REGIME_DEFS, regime_at

    regime_id = params["regime"]
    regime_def = next((r for r in REGIME_DEFS if r.id == regime_id), None)
    if regime_def is None:
        return list(entries)
    kept: list[tuple[int, str]] = []
    for i, side in entries:
        reg = regime_at(candles[i].timestamp_ms, regime_def, macro)
        if side == "LONG" and reg == "risk_on":
            kept.append((i, side))
        elif side == "SHORT" and reg == "risk_off":
            kept.append((i, side))
    return kept


_FILTERS = {
    "slow_ma_regime": _apply_slow_ma_regime,
    "atr_band": _apply_atr_band,
    "funding_extreme": _apply_funding_extreme,
    "oi_momentum": _apply_oi_momentum,
    "macro_regime": _apply_macro_regime,
}


def _apply_filters(candles, entries, filters: tuple[dict, ...], context=None) -> list[tuple[int, str]]:
    out = list(entries)
    for filt in filters:
        fn = _FILTERS[filt["name"]]
        out = fn(candles, out, context, filt["params"]) if filt["name"] in ("funding_extreme", "oi_momentum", "macro_regime") else fn(candles, out, filt["params"])
    return out


def _score_records(candles, entries, exit_name: str, exit_params: dict) -> list[dict]:
    out: list[dict] = []
    for i, side in entries:
        res = single_trade_r(candles, i, side, exit_name, exit_params)
        if res is None:
            continue
        net_r, atr_frac = res
        out.append({"i": i, "side": side, "net_r": net_r, "atr_frac": atr_frac})
    return out


def _summary(records: list[dict]) -> dict:
    rs = [r["net_r"] for r in records]
    s = summarize_r(rs)
    return {
        "trade_count": s.trade_count,
        "total_r": s.total_r,
        "expectancy_r": s.expectancy_r,
        "profit_factor": s.profit_factor,
        "max_drawdown_r": s.max_drawdown_r,
        "sharpe": _sharpe(rs) if len(rs) >= 2 else 0.0,
        "skew": _skew(rs) if len(rs) >= 2 else 0.0,
        "kurtosis": _kurtosis(rs) if len(rs) >= 2 else 3.0,
        "long_trade_count": sum(1 for r in records if r["side"] == "LONG"),
        "short_trade_count": sum(1 for r in records if r["side"] == "SHORT"),
        "long_total_r": round(sum(r["net_r"] for r in records if r["side"] == "LONG"), 4),
        "short_total_r": round(sum(r["net_r"] for r in records if r["side"] == "SHORT"), 4),
    }


def _evaluate_records(candles, config: ExploreConfig, context=None) -> dict:
    long_entries = _rule_entries(candles, config.long_rule, "LONG")
    short_entries = _rule_entries(candles, config.short_rule, "SHORT")
    combined = _apply_filters(candles, sorted(long_entries + short_entries), config.filters, context)
    combined = nonoverlap(combined, config.h)
    twin = _apply_filters(candles, sorted(long_entries), config.filters, context)
    twin = nonoverlap(twin, config.h)

    combined_records = _score_records(candles, combined, config.exit_name, config.exit_params)
    twin_records = _score_records(candles, twin, config.exit_name, config.exit_params)

    metrics = _summary(combined_records)
    twin_metrics = _summary(twin_records)
    metrics.update({
        "twin_trade_count": twin_metrics["trade_count"],
        "twin_total_r": twin_metrics["total_r"],
        "twin_expectancy_r": twin_metrics["expectancy_r"],
        "twin_profit_factor": twin_metrics["profit_factor"],
        "twin_max_drawdown_r": twin_metrics["max_drawdown_r"],
        "twin_long_trade_count": twin_metrics["long_trade_count"],
        "twin_short_trade_count": twin_metrics["short_trade_count"],
        "twin_long_total_r": twin_metrics["long_total_r"],
        "twin_short_total_r": twin_metrics["short_total_r"],
        "twin_delta_total_r": round(metrics["total_r"] - twin_metrics["total_r"], 4),
        "twin_delta_expectancy_r": round(metrics["expectancy_r"] - twin_metrics["expectancy_r"], 4),
    })

    long_records = [r for r in combined_records if r["side"] == "LONG"]
    short_records = [r for r in combined_records if r["side"] == "SHORT"]
    metrics.update({
        "long_expectancy_r": summarize_r([r["net_r"] for r in long_records]).expectancy_r,
        "short_expectancy_r": summarize_r([r["net_r"] for r in short_records]).expectancy_r,
    })
    return {
        "records": combined_records,
        "twin_records": twin_records,
        "metrics": metrics,
        "long_records": long_records,
        "short_records": short_records,
    }


def evaluate_config(candles, config: ExploreConfig, context=None) -> dict:
    scored = _evaluate_records(candles, config, context)
    out = {
        "label": config.label,
        "timeframe": config.timeframe,
        "long_rule": config.long_rule,
        "short_rule": config.short_rule,
        "filters": config.filters,
        "exit_name": config.exit_name,
        "exit_params": config.exit_params,
        "h": config.h,
        "group": config.group,
        "axis": config.axis,
        "metrics": scored["metrics"],
        "records": scored["records"],
        "twin_records": scored["twin_records"],
    }
    return out


def run_explore(configs, explore_by_tf: dict[str, list], context_by_tf: dict | None = None) -> list[dict]:
    rows = []
    for config in configs:
        ctx = None if context_by_tf is None else context_by_tf.get(config.timeframe)
        row = evaluate_config(explore_by_tf[config.timeframe], config, ctx)
        rows.append(row)
    rows.sort(key=lambda r: r["metrics"]["total_r"], reverse=True)
    trial_srs = [row["metrics"]["sharpe"] for row in rows if row["metrics"]["trade_count"] >= 2]
    n_trials = len(rows)
    compact = []
    for row in rows:
        compact_row = {k: row[k] for k in (
            "label", "timeframe", "long_rule", "short_rule", "filters",
            "exit_name", "exit_params", "h", "group", "axis", "metrics"
        )}
        compact_row["dsr"] = deflated_sharpe(
            row["metrics"]["sharpe"],
            max(2, row["metrics"]["trade_count"]),
            row["metrics"]["skew"],
            row["metrics"]["kurtosis"],
            trial_srs,
            n_trials,
        )
        compact.append(compact_row)
    return compact
