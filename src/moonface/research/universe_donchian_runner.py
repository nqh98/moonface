# src/moonface/research/universe_donchian_runner.py
"""Bespoke runner for the universe_donchian domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) but drives the
universe-expansion dominance ladder + walk-forward itself: the generic
runner.run cannot express the dynamic-universe portfolio + static-basket
control-dominance gate. The generic runner skips any domain whose config.runner
is neither None nor 'generic'."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import replace
from pathlib import Path

from moonface.core.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.kernel.spec import spec_from_json, spec_hash
from moonface.kernel.store import Store
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.research.universe_data import (fetch_daily_klines,
                                             fetch_funding_rates,
                                             fetch_perp_candles,
                                             list_um_perp_symbols)
from moonface.research.universe_donchian import (
    DOMAIN, GROSS, Position, _qualifies, build_membership, btc_reference_spec,
    evaluate_dominant, is_alt_perp, lockbox_dominant, simulate_portfolio,
    stage1_of, stage2_of, stage4_of, universe_donchian_specs)
from moonface.research.universe_donchian_wf import stage35_of, walk_forward

UNIVERSE_DONCHIAN_DOMAIN = DOMAIN
UNIVERSE_DONCHIAN_START_MS = 1_609_459_200_000   # 2021-01-01 UTC
LOCKBOX_FRACTION = 0.2
_DAY_MS = 86_400_000

_LS_ENGINE = TrendParams(entry_n=40, trail_n=20, atr_period=14, k_stop=2.0,
                         long_only=False, fee_rate=0.00045, slippage=0.0005,
                         funding_enabled=True, exit_mode="trail")
_LONG_ONLY_ENGINE = replace(_LS_ENGINE, long_only=True)


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 4-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - UNIVERSE_DONCHIAN_START_MS) * LOCKBOX_FRACTION)
    if store.domain(UNIVERSE_DONCHIAN_DOMAIN, 1) is None:
        store.register_domain(UNIVERSE_DONCHIAN_DOMAIN, 1, "active",
                              {"runner": "universe_donchian"},
                              UNIVERSE_DONCHIAN_START_MS, now_ms, fence_ts)
        store.insert_grid(UNIVERSE_DONCHIAN_DOMAIN, 1, universe_donchian_specs())


def _utc_midnight(ts_ms: int) -> int:
    return ts_ms - (ts_ms % _DAY_MS)


def _daily_funding_map(points, start_ms, end_ms):
    """{utc_midnight(funding_time): sum(rate)} over the window."""
    out: dict[int, float] = {}
    for t, rate in points:
        if start_ms <= t < end_ms:
            out[_utc_midnight(t)] = out.get(_utc_midnight(t), 0.0) + rate
    return out


def _load_engine_trades(symbols, start_ms, end_ms, cache_dir, engine):
    """For each symbol: 4h candles + funding -> simulate_donchian -> Position list
    in day-space (entry_day/exit_day floored to UTC midnight). Returns
    {symbol: list[Position]} and {symbol: {day_ts: close}}."""
    positions: dict[str, list[Position]] = {}
    closes: dict[str, dict[int, float]] = {}
    for sym in symbols:
        candles = fetch_perp_candles(sym, "4h", start_ms, end_ms, cache_dir)
        if len(candles) < engine.entry_n + 2:
            continue
        funding = fetch_funding_rates(sym, start_ms, end_ms, cache_dir)
        trades = simulate_donchian(candles, engine, funding)
        positions[sym] = [Position(t.side, _utc_midnight(candles[t.entry_index].timestamp_ms),
                                   _utc_midnight(candles[t.exit_index].timestamp_ms),
                                   t.r_multiple) for t in trades]
        closes[sym] = {_utc_midnight(c.timestamp_ms): c.close for c in candles}
    return positions, closes


def _simulate_cfg(cfg, daily, calendar, positions, closes, funding_daily):
    membership, book = build_membership(daily, calendar, cfg)
    returns = simulate_portfolio(calendar, membership, book, positions, closes,
                                 funding_daily, gross=GROSS)
    return returns


def run_domain(store: Store, cache_dir: str, out_root: Path) -> str:
    d = store.domain(UNIVERSE_DONCHIAN_DOMAIN, 1)
    start_ms, end_ms, fence_ts = d["start_ms"], d["end_ms"], d["fence_ts"]
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(UNIVERSE_DONCHIAN_DOMAIN, 1)]
    grid_size = len(specs)                       # == N_TRIALS == 4

    # 1. Universe + daily klines (quote volume), alt-only.
    all_symbols = [s for s in list_um_perp_symbols() if is_alt_perp(s)]
    daily = {s: fetch_daily_klines(s, start_ms, end_ms, cache_dir)
             for s in all_symbols}
    daily = {s: rows for s, rows in daily.items() if rows}

    # 2. Unified daily calendar + fence index.
    calendar = sorted({r.ts_ms for rows in daily.values() for r in rows
                       if start_ms <= r.ts_ms < end_ms})
    fence_idx = bisect_left(calendar, fence_ts)

    # 3. Candidate set: symbols that ever clear the liquidity+age floor (bounds
    #    the expensive 4h+funding+engine fetches to liquid alts only).
    candidate_filters = {
        (spec.entry["params"]["min_liquidity_usd"],
         spec.entry["params"]["min_age_days"],
         spec.entry["params"]["lookback_days"])
        for spec in specs
    }
    candidates = [s for s, rows in daily.items()
                  if any(_qualifies(rows, t, min_liq, min_age, lookback)
                         for min_liq, min_age, lookback in candidate_filters
                         for t in calendar)]

    positions, closes = _load_engine_trades(candidates, start_ms, end_ms,
                                            cache_dir, _LS_ENGINE)
    # Per-symbol daily funding (sum of 8h prints per UTC day).
    funding_daily = {s: _daily_funding_map(fetch_funding_rates(s, start_ms, end_ms, cache_dir),
                                           start_ms, end_ms) for s in candidates}

    # 4. BTC reference (non-gating), routed through the same simulator as a
    #    single-symbol static book with the long-only deployed engine.
    btc_positions, btc_closes = _load_engine_trades(["BTCUSDT"], start_ms, end_ms,
                                                    cache_dir, _LONG_ONLY_ENGINE)
    btc_membership, btc_book = build_membership(
        {"BTCUSDT": fetch_daily_klines("BTCUSDT", start_ms, end_ms, cache_dir)},
        calendar, btc_reference_spec().entry["params"])
    btc_funding_daily = {
        "BTCUSDT": _daily_funding_map(
            fetch_funding_rates("BTCUSDT", start_ms, end_ms, cache_dir),
            start_ms,
            end_ms,
        )
    }
    btc_returns = simulate_portfolio(calendar, btc_membership, btc_book,
                                     btc_positions, btc_closes,
                                     btc_funding_daily, gross=GROSS)

    # 5. Per-spec: build treatment + control curves, evaluate stages 1/2/3.5.
    rows: list[dict] = []
    for spec in specs:
        cfg = spec.entry["params"]
        t_ret = _simulate_cfg(cfg, daily, calendar, positions, closes,
                              funding_daily)
        c_ret = _simulate_cfg({**cfg, "rank": "static"}, daily, calendar,
                              positions, closes, funding_daily)
        screen_trades = _screen_pooled_trades(daily, positions, calendar, fence_idx, cfg)
        m = evaluate_dominant(t_ret, c_ret, screen_trades, fence_idx, SCREEN_FRACTION)
        rows.append({"spec_hash": spec_hash(spec), "spec": spec, "m": m,
                     "wf": None, "stage": "research", "t_ret": t_ret, "c_ret": c_ret})
        if not stage1_of(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_of(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward(t_ret[:fence_idx], c_ret[:fence_idx])
        rows[-1]["wf"] = wf
        rows[-1]["stage"] = "wf_pass" if stage35_of(wf) else "rejected_wf"

    # 6. DSR (stage 3) across survivors; trial variance from ALL specs.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    dsr: dict[str, float] = {}
    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        m = r["m"]
        value = deflated_sharpe(m["research_sharpe"], m["research_trades"],
                                m["research_skew"], m["research_kurtosis"],
                                all_sharpes, grid_size)
        r["dsr"] = round(value, 6)
        if r["dsr"] >= DSR_THRESHOLD:
            dsr[r["spec_hash"]] = r["dsr"]
        else:
            r["stage"] = "rejected_dsr"

    # 7. One-touch lockbox (stage 4) for every DSR survivor.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if survivors:
        store.touch_lockbox(UNIVERSE_DONCHIAN_DOMAIN, 1)   # set-once for the domain
        for r in survivors:
            cfg = r["spec"].entry["params"]
            t_tail = r["t_ret"][fence_idx:]
            c_tail = r["c_ret"][fence_idx:]
            tail_trades = _screen_pooled_trades(daily, positions, calendar, fence_idx,
                                                cfg, tail_only=True)
            tail = lockbox_dominant(t_tail, c_tail, tail_trades)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(UNIVERSE_DONCHIAN_DOMAIN, 1, verdict)
    reference = _reference_metrics(btc_returns, fence_idx)
    _write_verdict(out_root, verdict, rows, dsr, reference)
    return verdict


def _screen_pooled_trades(daily, positions, calendar, fence_idx, cfg, tail_only=False):
    """Engine r_multiples for trades whose symbol was eligible per the treatment
    cfg at the trade's entry day, with the entry day in the screen window
    (research[:fence]) — or the lockbox tail (research[fence:]) when tail_only.
    Eligibility is read from the weekly membership (rebuilt once here) so it
    matches what the portfolio simulator actually traded."""
    membership, _ = build_membership(daily, calendar, cfg)
    lo = fence_idx if tail_only else 0
    hi = fence_idx if not tail_only else len(calendar)
    out: list[float] = []
    for day_idx in range(lo, hi):
        ts = calendar[day_idx]
        elig = membership.get(ts, frozenset())
        for sym, trades in positions.items():
            if sym not in elig:
                continue
            for pos in trades:
                if pos.entry_day == ts:
                    out.append(pos.r_multiple)
    return out


def _reference_metrics(btc_returns, fence_idx):
    from moonface.core.metrics import equity_summary_from_returns
    full = equity_summary_from_returns(btc_returns)
    tail = equity_summary_from_returns(btc_returns[fence_idx:])
    return {"full_mar": full.mar, "full_sharpe": full.sharpe,
            "full_dd": full.max_drawdown, "tail_mar": tail.mar,
            "tail_sharpe": tail.sharpe, "tail_dd": tail.max_drawdown}


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float], reference: dict) -> None:
    lines = [
        "# universe_donchian v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {UNIVERSE_DONCHIAN_DOMAIN} (frozen Donchian engine on a"
        " dynamic top-5 alt universe by abnormal 24h quote-volume expansion, vs"
        " a static broad-basket control)",
        "- **Construction:** simulate_donchian(entry_n=40, trail_n=20 @ 4h,"
        " long_only=False) on universe_data alt perps; COST_FRACTION=0.001"
        " round-trip + funding; top-5/30d-ratio screener default.",
        "- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5,"
        " DSR(>=0.95, n_trials=4), and 4 AND strictly dominate its static-basket"
        " control on portfolio MAR & Sharpe at holdout, WF aggregate, and lockbox"
        " tail.",
        f"- **BTC/USDT deployed reference (non-gating):** full MAR"
        f" {reference['full_mar']:.3f}, tail MAR {reference['tail_mar']:.3f},"
        f" tail DD {reference['tail_dd']:.3f}.",
        "",
        "| screener | final stage | screen n | holdout trt MAR | WF folds |"
        " DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        label = (f"{r['spec'].entry['params'].get('top_n')}x"
                 f"{r['spec'].entry['params'].get('lookback_days')}d"
                 f"-{r['spec'].entry['params'].get('metric')}")
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(f"| {label} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | "
                     f"{dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2 universe"
              " rule, no filter relaxation, no long-only flip, no exit change, no"
              " top-N re-tuning. The universe-expansion lever is terminal for the"
              " frozen Donchian engine on a closed-negative verdict."]
    d = out_root / UNIVERSE_DONCHIAN_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
