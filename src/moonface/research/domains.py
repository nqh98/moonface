# src/moonface/research/domains.py
from __future__ import annotations

from moonface.core.exits import EXIT_REGISTRY
from moonface.kernel.spec import HypothesisSpec
from moonface.kernel.store import Store

_DAY_MS = 86_400_000
YEARS = 3.0
LOCKBOX_FRACTION = 0.2  # final 20% of the window, frozen at init

# Pre-registered grids (design spec §4). Frozen by the store after first insert:
# editing these after a domain has started requires a new domain version.
FRACTIONS = [0.005, 0.01, 0.02]
TRANSFER_FRACTION = 0.01

FADE_GRID = [{"window": 60, "z_thr": 1.5}, {"window": 60, "z_thr": 2.0},
             {"window": 180, "z_thr": 1.5}, {"window": 180, "z_thr": 2.0}]
FLIP_GRID = [{"debounce": 6}]
BASIS_GRID = [{"window": 180, "pct": 5}, {"window": 180, "pct": 10},
              {"window": 360, "pct": 5}, {"window": 360, "pct": 10}]

RELAXED_BUDGET_V2_ENTRIES = [
    ("basis_discount_reversion", {"window": 180, "pct": 5}),
    ("funding_fade", {"window": 180, "z_thr": 2.0}),
]
RELAXED_BUDGET_V2_EXITS = [
    ("fixed_bracket", {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}),
    ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0}),
    ("atr_trail", {"atr_period": 14, "k_trail": 3.0, "max_bars": 48}),
]
RELAXED_BUDGET_V2_FRACTIONS = [0.01]

TRANSFER_ENTRIES = [
    ("ma_cross", [{"fast": 10, "slow": 50}, {"fast": 20, "slow": 100},
                  {"fast": 50, "slow": 200}]),
    ("price_vs_ma", [{"period": 50}, {"period": 100}, {"period": 200}]),
    ("roc_sign", [{"period": 12}, {"period": 24}, {"period": 48}]),
    ("donchian_break", [{"n": 20}, {"n": 55}, {"n": 100}]),
    ("atr_channel_break", [{"k": 1.0, "atr_period": 14},
                           {"k": 1.5, "atr_period": 14},
                           {"k": 2.0, "atr_period": 14}]),
    ("smc_continuation", [{"lookback": 10}, {"lookback": 30}]),
    ("reversion_in_range", [{"period": 14, "low": 30, "high": 70},
                            {"period": 14, "low": 20, "high": 80}]),
]

BTC_PERP = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h",
            "funding_symbol": "BTC/USDT:USDT", "spot_symbol": "BTC/USDT"}
TRANSFER_ASSETS = [
    {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "4h"},
    {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "4h"},
]

# vol_regime and seasonality were tested to death in the ap_* lineages and are
# shelved as placeholders; lead_lag is the one registered family never tested.
RETIRED_SUBDOMAINS = ["new_families.vol_regime", "new_families.seasonality"]

LEAD_LAG_ASSET = {**BTC_PERP, "feature_symbol": "ETH/USDT:USDT"}
LEAD_LAG_ENTRIES = [
    ("eth_lead_momentum", {"window": 180, "lookback": 12, "z_thr": 1.5}),
    ("eth_lead_momentum", {"window": 180, "lookback": 24, "z_thr": 1.5}),
]
LEAD_LAG_EXITS = RELAXED_BUDGET_V2_EXITS  # identical exit set, no new shapes
LEAD_LAG_FRACTIONS = [0.01]

# Positioning family over the Binance Vision metrics archive (free 5-min
# open-interest / long-short / taker-flow history since 2020-09 — the live
# REST endpoints only keep ~30d, which is why this family was shelved until
# 2026-06-11). One mechanism-chosen direction per family; no spot/funding
# legs so only candles + one metrics series are loaded per hypothesis.
_BTC_PERP_BARE = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
                  "timeframe": "4h"}
POSITIONING_ENTRIES = [
    ("oi_flush_reversal", {"window": 180, "lookback": 6, "z_thr": 1.5},
     "sum_open_interest"),
    ("oi_flush_reversal", {"window": 180, "lookback": 24, "z_thr": 1.5},
     "sum_open_interest"),
    ("oi_build_momentum", {"window": 180, "lookback": 6, "z_thr": 1.5},
     "sum_open_interest"),
    ("oi_build_momentum", {"window": 180, "lookback": 24, "z_thr": 1.5},
     "sum_open_interest"),
    ("toptrader_follow", {"window": 180, "z_thr": 1.5},
     "sum_toptrader_long_short_ratio"),
    ("toptrader_follow", {"window": 180, "z_thr": 2.0},
     "sum_toptrader_long_short_ratio"),
    ("taker_flow_momentum", {"window": 180, "z_thr": 1.5},
     "sum_taker_long_short_vol_ratio"),
    ("taker_flow_momentum", {"window": 180, "z_thr": 2.0},
     "sum_taker_long_short_vol_ratio"),
]
# Full standard exit registry (10 shapes), like multi_asset_transfer: this is
# a brand-new mechanism, so it gets the standard breadth, not the trimmed set.
POSITIONING_FRACTIONS = [0.01]

# Transfer test of the one family that led positioning_btc (oi_build_momentum,
# DSR 0.30 — the program's strongest corrected signal, still noise by the
# gate). Confirmation on independent assets: only the frozen oi_build entries
# transfer (narrow grid keeps the comparison count honest); exits get the
# standard breadth because exit shape need not transfer across assets.
POSITIONING_TRANSFER_ASSETS = [
    {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "4h",
     "metrics_field": "sum_open_interest"},
    {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "4h",
     "metrics_field": "sum_open_interest"},
]
POSITIONING_TRANSFER_ENTRIES = [
    ("oi_build_momentum", {"window": 180, "lookback": 6, "z_thr": 1.5}),
    ("oi_build_momentum", {"window": 180, "lookback": 24, "z_thr": 1.5}),
]

# Funding-fade transfer (spec 2026-06-15): the closed program's single best OOS
# construction — funding_fade {w:60,z:1.5} (+76.7R OOS / +1.13R exp on BTC,
# rejected ONLY by the fixed -15R cap) — re-tested under the MAR/sizing ladder
# on assets the funding probe never touched. BTC is the contaminated/selected
# asset and is DELIBERATELY ABSENT from the gated grid; its Q1 reference lives
# in research/funding_fade_ref.py and never spends a lockbox.
FUNDING_FADE_TRANSFER_ASSETS = [
    {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "ETH/USDT:USDT"},
    {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "4h",
     "funding_symbol": "SOL/USDT:USDT"},
]
FUNDING_FADE_TRANSFER_ENTRY = ("funding_fade", {"window": 60, "z_thr": 1.5})
FUNDING_FADE_TRANSFER_EXITS = [
    ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0}),
    ("atr_trail", {"atr_period": 14, "k_trail": 3.0, "max_bars": 48}),
]


def _exit_specs() -> list[tuple[str, dict]]:
    return [(name, params)
            for name, (_fn, grid) in EXIT_REGISTRY.items() for params in grid]


def relaxed_budget_grid() -> list[HypothesisSpec]:
    entries = ([("funding_fade", p) for p in FADE_GRID]
               + [("funding_flip", p) for p in FLIP_GRID]
               + [("basis_discount_reversion", p) for p in BASIS_GRID])
    return [HypothesisSpec(domain="relaxed_budget_btc", version=1, asset=BTC_PERP,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp}, fraction=f)
            for fam, ep in entries for en, xp in _exit_specs() for f in FRACTIONS]


def relaxed_budget_v2_grid() -> list[HypothesisSpec]:
    return [HypothesisSpec(domain="relaxed_budget_btc", version=2, asset=BTC_PERP,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp}, fraction=f)
            for fam, ep in RELAXED_BUDGET_V2_ENTRIES
            for en, xp in RELAXED_BUDGET_V2_EXITS
            for f in RELAXED_BUDGET_V2_FRACTIONS]


def multi_asset_grid() -> list[HypothesisSpec]:
    return [HypothesisSpec(domain="multi_asset_transfer", version=1, asset=a,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp},
                           fraction=TRANSFER_FRACTION)
            for a in TRANSFER_ASSETS
            for fam, grid in TRANSFER_ENTRIES for ep in grid
            for en, xp in _exit_specs()]


def positioning_grid() -> list[HypothesisSpec]:
    return [HypothesisSpec(domain="positioning_btc", version=1,
                           asset={**_BTC_PERP_BARE, "metrics_field": field},
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp}, fraction=f)
            for fam, ep, field in POSITIONING_ENTRIES
            for en, xp in _exit_specs()
            for f in POSITIONING_FRACTIONS]


def positioning_transfer_grid() -> list[HypothesisSpec]:
    return [HypothesisSpec(domain="positioning_transfer", version=1, asset=a,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp},
                           fraction=TRANSFER_FRACTION)
            for a in POSITIONING_TRANSFER_ASSETS
            for fam, ep in POSITIONING_TRANSFER_ENTRIES
            for en, xp in _exit_specs()]


def funding_fade_transfer_grid() -> list[HypothesisSpec]:
    fam, ep = FUNDING_FADE_TRANSFER_ENTRY
    return [HypothesisSpec(domain="funding_fade_transfer", version=1, asset=a,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp},
                           fraction=TRANSFER_FRACTION)
            for a in FUNDING_FADE_TRANSFER_ASSETS
            for en, xp in FUNDING_FADE_TRANSFER_EXITS]


def lead_lag_grid() -> list[HypothesisSpec]:
    return [HypothesisSpec(domain="new_families.lead_lag", version=1,
                           asset=LEAD_LAG_ASSET,
                           entry={"family": fam, "params": ep},
                           exit={"name": en, "params": xp}, fraction=f)
            for fam, ep in LEAD_LAG_ENTRIES
            for en, xp in LEAD_LAG_EXITS
            for f in LEAD_LAG_FRACTIONS]


def register_v1(store: Store, now_ms: int) -> list[str]:
    """Idempotent: domains already present are skipped. The data window and
    lockbox fence are frozen here; later runs reuse the stored values."""
    start_ms = now_ms - int(YEARS * 365 * _DAY_MS)
    fence_ts = now_ms - int(YEARS * 365 * _DAY_MS * LOCKBOX_FRACTION)
    plans = [
        ("relaxed_budget_btc", 1, "active", {"assets": [BTC_PERP]},
         relaxed_budget_grid),
        ("multi_asset_transfer", 1, "active", {"assets": TRANSFER_ASSETS},
         multi_asset_grid),
        ("relaxed_budget_btc", 2, "active", {"assets": [BTC_PERP]},
         relaxed_budget_v2_grid),
        ("new_families.lead_lag", 1, "active", {"assets": [LEAD_LAG_ASSET]},
         lead_lag_grid),
        ("positioning_btc", 1, "active",
         {"assets": [{**_BTC_PERP_BARE, "metrics_field": f}
                     for f in ("sum_open_interest",
                               "sum_toptrader_long_short_ratio",
                               "sum_taker_long_short_vol_ratio")]},
         positioning_grid),
        ("positioning_transfer", 1, "active",
         {"assets": POSITIONING_TRANSFER_ASSETS}, positioning_transfer_grid),
        ("funding_fade_transfer", 1, "active",
         {"assets": FUNDING_FADE_TRANSFER_ASSETS}, funding_fade_transfer_grid),
    ] + [(n, 1, "shelved", {"assets": []}, None) for n in RETIRED_SUBDOMAINS]
    registered: list[str] = []
    for name, version, status, config, grid_fn in plans:
        if store.domain(name, version) is not None:
            continue
        store.register_domain(name, version, status, config, start_ms, now_ms, fence_ts)
        if grid_fn is not None:
            store.insert_grid(name, version, grid_fn())
        registered.append(name)
    return registered


def reconcile_new_families(store: Store) -> list[str]:
    """Bring a pre-existing store in line with the 2026-06-11 spec: lift the
    lead_lag placeholder (blocked, empty grid) to active with the frozen
    pre-registered grid, and shelve the placeholders already falsified via the
    ap_* lineages. The domain's frozen window and fence are never changed.
    Idempotent."""
    changed: list[str] = []
    d = store.domain("new_families.lead_lag", 1)
    if d is not None and d["status"] == "blocked" and d["grid_size"] == 0:
        store.insert_grid("new_families.lead_lag", 1, lead_lag_grid())
        store.set_domain_status("new_families.lead_lag", 1, "active")
        changed.append("new_families.lead_lag")
    for name in RETIRED_SUBDOMAINS:
        d = store.domain(name, 1)
        if d is not None and d["status"] == "blocked":
            store.set_domain_status(name, 1, "shelved")
            changed.append(name)
    return changed


def reregister_domain(store: Store, name: str, from_version: int) -> int:
    """Re-register a closed domain's frozen grid as the next version, keeping
    the window, fence, and config verbatim. Only legal when the source
    version's lockbox tail was never evaluated (no row ever reached
    lockbox_pass/lockbox_fail) — e.g. a domain closed after an error boundary
    spent its one-touch on zero corrected survivors. A tail any hypothesis was
    actually scored on stays spent forever."""
    import dataclasses

    from moonface.kernel.spec import spec_from_json

    d = store.domain(name, from_version)
    if d is None:
        raise ValueError(f"unknown domain {name} v{from_version}")
    if not d["status"].startswith("closed"):
        raise ValueError(f"{name} v{from_version} is '{d['status']}';"
                         " only a closed version can be re-registered")
    if store.max_version(name) != from_version:
        raise ValueError(f"{name} already has a version after {from_version};"
                         " refusing to fork the lineage")
    counts = store.counts(name, from_version)
    if counts.get("lockbox_pass", 0) or counts.get("lockbox_fail", 0):
        raise ValueError(
            f"{name} v{from_version} evaluated hypotheses on its lockbox tail;"
            " that tail is contaminated and cannot be re-registered")
    new_version = from_version + 1
    specs = [dataclasses.replace(spec_from_json(r["spec_json"]),
                                 version=new_version)
             for r in store.rows(name, from_version)]
    store.register_domain(name, new_version, "active", d["config"],
                          d["start_ms"], d["end_ms"], d["fence_ts"])
    store.insert_grid(name, new_version, specs)
    return new_version
