"""Frozen v3 evaluation splits and trade record shape."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.core.risk import atr
from moonface.core.stats import series_fingerprint
from moonface.models.engine.calibration import PANEL_FLOOR, scoring_pass
from moonface.models.engine.confluence import BASE_THRESHOLD
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.config_v3 import engine_hash_v3
from moonface.models.engine.v3.matrix import MECHANISMS, REGIME_MECHANISM, select_mechanism
from moonface.models.engine.v3.mechanisms.base import build_context
from moonface.models.engine.v3.sizing import size_from_quality
from moonface.models.engine.v3.regime import VolState, classify_regime
from moonface.models.engine.position import PositionState, manage_position, open_position
from moonface.models.engine.repair import (
    PURGE_MS,
    block_ci_q,
    _pava_blocks,
    qualifier_stream,
    replay_metrics,
    segment_panel,
)

SPAN_START_TS_MS = 1577836800000
TRAIN_END_TS_MS = 1704067200000
SEALED_START_TS_MS = 1751328000000
SPAN_END_TS_MS = 1782316800000
K_STOP = 2.0
K_TRAIL = 3.0
MAX_BARS = 96
ATR_PERIOD = 14
N_MECHANISMS = 3
N_ACTIVE_CELLS = 9
EFFECTIVE_TRIALS = 12
FAMILY_ALPHA = 0.05
CI_LO_Q = FAMILY_ALPHA / EFFECTIVE_TRIALS / 2
CI_HI_Q = 1 - CI_LO_Q
MIN_MECH_TRADES = 30
MIN_CELL_TRADES = 30
MIN_TRANSFER_TRADES = 20
LOOKBACK = 400
ASSETS = {
    "BTC": {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"},
    "ETH": {"exchange": "binance", "symbol": "ETH/USDT:USDT", "timeframe": "1h"},
    "SOL": {"exchange": "binance", "symbol": "SOL/USDT:USDT", "timeframe": "1h"},
}
EVAL_LABEL = (
    "v3 backtest evaluation — pre-registered; read-only; no capital gating; "
    "promotion is a human decision"
)
VERDICTS = (
    "CLOSED_NEGATIVE_VALIDATION",
    "CLOSED_NEGATIVE_SEALED_BTC",
    "CLOSED_NEGATIVE_TRANSFER",
    "ALL_GATES_PASSED_HUMAN_DECISION_PENDING",
)


@dataclass(frozen=True)
class V3Trade:
    entry_index: int
    exit_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    direction: int
    mechanism: str
    quality: float
    risk_fraction: float
    net_r: float
    bars_held: int
    exit_reason: str
    cell: str


def segment_v3(trades: list[V3Trade]) -> tuple[dict[str, list[V3Trade]], int]:
    return segment_panel(trades, TRAIN_END_TS_MS, SEALED_START_TS_MS, PURGE_MS)


def simulate_bracket_v3(
    candles: list[Candle],
    entry_index: int,
    direction: int,
    quality: float,
    mechanism: str,
    cell: str,
    cfg_v22: EngineConfig,
) -> V3Trade | None:
    """Open at the entry close and manage bar-by-bar with the frozen v2.2 WT bracket."""
    j = entry_index
    tail = candles[max(0, j - cfg_v22.atr_period) : j + 1]
    step = open_position(
        tail,
        cfg_v22,
        direction,
        quality,
        cfg_v22.base_fraction,
        "WT",
    )
    pos = PositionState(
        direction=direction,
        entry_price=step.entry_price,
        stop=step.stop,
        extreme=step.extreme,
        atr_at_entry=step.atr_at_entry,
        fraction=cfg_v22.base_fraction,
        bars_held=0,
        profile="WT",
        target=step.target,
    )
    for k in range(j + 1, len(candles)):
        step = manage_position([candles[k]], cfg_v22, pos, 0, quality)
        if step.action == "EXIT":
            return V3Trade(
                entry_index=j,
                exit_index=k,
                entry_ts_ms=candles[j].timestamp_ms,
                exit_ts_ms=candles[k].timestamp_ms,
                direction=direction,
                mechanism=mechanism,
                quality=quality,
                risk_fraction=cfg_v22.base_fraction,
                net_r=step.realized_r if step.realized_r is not None else 0.0,
                bars_held=step.bars_held if step.bars_held is not None else 0,
                exit_reason=step.reason,
                cell=cell,
            )
        pos = PositionState(
            direction=pos.direction,
            entry_price=pos.entry_price,
            stop=step.stop,
            extreme=step.extreme,
            atr_at_entry=pos.atr_at_entry,
            fraction=pos.fraction,
            bars_held=step.bars_held if step.bars_held is not None else 0,
            profile="WT",
            target=step.target,
        )
    return None


def fit_panel(
    candles: list[Candle],
    cfg_v3: EngineConfigV3,
    cfg_v22: EngineConfig,
    lookback: int = LOOKBACK,
) -> list[V3Trade]:
    """Floor-free overlapping trigger stream used for train-window fitting."""
    panel: list[V3Trade] = []
    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        window = candles[max(0, i - lookback + 1) : i + 1]
        idx = len(window) - 1
        regime = classify_regime(window, cfg_v3)
        if regime.vol_state == VolState.EXTREME:
            continue
        name = select_mechanism(regime)
        if name is None:
            continue
        ctx = build_context(window, idx, cfg_v3)
        sig = MECHANISMS[name].evaluate(ctx, regime)
        if sig.direction == 0:
            continue
        cell = f"{regime.dir_state.value}/{regime.vol_state.value}"
        trade = simulate_bracket_v3(
            candles, i, sig.direction, sig.quality, name, cell, cfg_v22
        )
        if trade is not None:
            panel.append(trade)
    return panel


_DEFAULT_FLOOR = {
    "BREAKOUT": "q_floor_breakout",
    "PULLBACK": "q_floor_pullback",
    "REVERSION": "q_floor_reversion",
}


def fit_q_floors(train: list[V3Trade], cfg_v3: EngineConfigV3) -> dict[str, float]:
    """Lowest quality at which isotonic E[R] becomes non-negative."""
    floors: dict[str, float] = {}
    for name, attr in _DEFAULT_FLOOR.items():
        default = getattr(cfg_v3, attr)
        rows = sorted(
            ((t.quality, t.net_r) for t in train if t.mechanism == name),
            key=lambda p: p[0],
        )
        if len(rows) < MIN_MECH_TRADES:
            floors[name] = default
            continue
        qs = [q for q, _ in rows]
        means = [r for _, r in rows]
        weights = [1.0] * len(rows)
        blocks = _pava_blocks(means, weights)
        fitted: list[float] = []
        for mean, _, size in blocks:
            fitted.extend([mean] * int(size))
        floor = default
        for q, f in zip(qs, fitted):
            if f >= 0.0:
                floor = q
                break
        else:
            floor = 1.0
        floors[name] = floor
    return floors


def prune_cells(train: list[V3Trade]) -> dict[tuple, str | None]:
    """Copy of REGIME_MECHANISM with live cells pruned when underpowered or non-positive."""
    by_cell: dict[str, list[float]] = {}
    for trade in train:
        by_cell.setdefault(trade.cell, []).append(trade.net_r)
    fitted: dict[tuple, str | None] = {}
    for (dir_state, vol_state), name in REGIME_MECHANISM.items():
        if name is None:
            fitted[(dir_state, vol_state)] = None
            continue
        cell = f"{dir_state.value}/{vol_state.value}"
        rs = by_cell.get(cell, [])
        keep = len(rs) >= MIN_CELL_TRADES and sum(rs) > 0.0
        fitted[(dir_state, vol_state)] = name if keep else None
    return fitted


def fitted_cfg(
    cfg_v3: EngineConfigV3,
    q_floors: dict[str, float],
) -> EngineConfigV3:
    return dataclasses.replace(
        cfg_v3,
        q_floor_breakout=q_floors["BREAKOUT"],
        q_floor_pullback=q_floors["PULLBACK"],
        q_floor_reversion=q_floors["REVERSION"],
    )


def decide_fitted(
    window: list[Candle],
    index: int,
    cfg_v3_fitted: EngineConfigV3,
    fitted_matrix: dict,
) -> tuple[str, int, float, float, str] | None:
    """decide_v3 logic with the fitted matrix + fitted q_floors."""
    regime = classify_regime(window, cfg_v3_fitted)
    if regime.vol_state == VolState.EXTREME:
        return None
    name = fitted_matrix.get((regime.dir_state, regime.vol_state))
    if name is None:
        return None
    ctx = build_context(window, index, cfg_v3_fitted)
    sig = MECHANISMS[name].evaluate(ctx, regime)
    if sig.direction == 0:
        return None
    frac = size_from_quality(name, sig.quality, cfg_v3_fitted)
    if frac == 0.0:
        return None
    cell = f"{regime.dir_state.value}/{regime.vol_state.value}"
    return (name, sig.direction, sig.quality, frac, cell)


def v3_stream(
    candles: list[Candle],
    cfg_v3_fitted: EngineConfigV3,
    fitted_matrix: dict,
    cfg_v22: EngineConfig,
    lookback: int = LOOKBACK,
) -> list[tuple[V3Trade, float]]:
    """One-position-at-a-time fitted stream; pairs carry atr_frac."""
    pairs: list[tuple[V3Trade, float]] = []
    busy_until = -1
    start = min(lookback, len(candles))
    for i in range(start, len(candles)):
        if i <= busy_until:
            continue
        window = candles[max(0, i - lookback + 1) : i + 1]
        decided = decide_fitted(window, len(window) - 1, cfg_v3_fitted,
                                fitted_matrix)
        if decided is None:
            continue
        name, direction, quality, frac, cell = decided
        trade = simulate_bracket_v3(candles, i, direction, quality, name,
                                    cell, cfg_v22)
        if trade is None:
            break
        trade = dataclasses.replace(trade, risk_fraction=frac)
        tail = candles[max(0, i - cfg_v22.atr_period):i + 1]
        close = candles[i].close
        atr_frac = atr(tail, cfg_v22.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs


def v3_metrics(pairs: list[tuple[V3Trade, float]], cfg_v22: EngineConfig) -> dict:
    """Unweighted gate metrics + size-weighted net-R diagnostic."""
    m = replay_metrics(pairs, cfg_v22)
    base = cfg_v22.base_fraction
    weighted = sum(
        t.net_r * (t.risk_fraction / base) for t, _ in pairs
    ) if base > 0 else 0.0
    m["size_weighted_net_r"] = round(weighted, 4)
    return m


def v22_pairs(
    candles: list[Candle],
    cfg_v22: EngineConfig,
    warmup: int,
) -> list:
    """Frozen v2.2 long-only trend stream over the full series."""
    rows = scoring_pass(cfg_v22, candles, warmup)
    return qualifier_stream(
        candles,
        cfg_v22,
        rows,
        lambda row: row.trend.score >= BASE_THRESHOLD,
    )


def split_pairs_by_window(
    pairs: list[tuple[V3Trade, float]],
    start_ts: int,
    end_ts: int,
) -> list[tuple[V3Trade, float]]:
    return [p for p in pairs if start_ts <= p[0].exit_ts_ms < end_ts]


def _mean_r(pairs: list[tuple[V3Trade, float]]) -> float | None:
    return sum(t.net_r for t, _ in pairs) / len(pairs) if pairs else None


def gate1_validation(val_pairs: list[tuple[V3Trade, float]],
                     baseline_val: dict) -> dict:
    m = v3_metrics(val_pairs, EngineConfig())
    ci = block_ci_q(val_pairs, lambda p: p[0].entry_index, _mean_r,
                    CI_LO_Q, CI_HI_Q)
    base_dd = baseline_val.get("max_dd_r", 0.0)
    passed = (
        len(val_pairs) >= PANEL_FLOOR
        and m["cost_stress"]["net_r_3x"] > 0
        and ci is not None
        and ci[0] > 0
        and abs(m["max_dd_r"]) <= abs(base_dd)
    )
    return {
        "n": m["n"],
        "net_r": m["net_r"],
        "net_r_3x": m["cost_stress"]["net_r_3x"],
        "max_dd_r": m["max_dd_r"],
        "baseline_max_dd_r": base_dd,
        "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
        "passed": passed,
    }


def gate2_sealed(sealed_pairs: list[tuple[V3Trade, float]],
                 baseline_sealed: dict) -> dict:
    m = v3_metrics(sealed_pairs, EngineConfig())
    base_dd = baseline_sealed.get("max_dd_r", 0.0)
    passed = (
        m["n"] > 0
        and m["cost_stress"]["net_r_3x"] > 0
        and abs(m["max_dd_r"]) <= abs(base_dd)
    )
    return {
        "n": m["n"],
        "net_r_3x": m["cost_stress"]["net_r_3x"],
        "max_dd_r": m["max_dd_r"],
        "baseline_max_dd_r": base_dd,
        "passed": passed,
    }


def _asset_leg(pairs: list[tuple[V3Trade, float]]) -> dict:
    m = v3_metrics(pairs, EngineConfig())
    return {"n": m["n"], "net_r_3x": m["cost_stress"]["net_r_3x"]}


def gate3_transfer(eth_pairs: list[tuple[V3Trade, float]],
                   sol_pairs: list[tuple[V3Trade, float]]) -> dict:
    eth = _asset_leg(eth_pairs)
    sol = _asset_leg(sol_pairs)
    passed = all(
        leg["n"] >= MIN_TRANSFER_TRADES and leg["net_r_3x"] > 0
        for leg in (eth, sol)
    )
    return {"eth": eth, "sol": sol, "passed": passed}


def fitted_matrix_payload(fitted_matrix: dict) -> dict:
    return {
        f"{d.value}/{v.value}": name
        for (d, v), name in sorted(fitted_matrix.items(), key=lambda kv: str(kv[0]))
    }


def build_eval_report(
    btc: list[Candle],
    eth: list[Candle],
    sol: list[Candle],
    cfg_v3: EngineConfigV3,
    cfg_v22: EngineConfig,
    warmup: int,
    lookback: int = LOOKBACK,
) -> dict:
    """Single registered evaluation with sealed protection."""
    fit_all = fit_panel(btc, cfg_v3, cfg_v22, lookback)
    fit_segs, _ = segment_v3(fit_all)
    train = fit_segs["train"]
    q_floors = fit_q_floors(train, cfg_v3)
    fitted_matrix = prune_cells(train)
    cfg_fit = fitted_cfg(cfg_v3, q_floors)

    btc_pairs = v3_stream(btc, cfg_fit, fitted_matrix, cfg_v22, lookback)
    val_pairs = split_pairs_by_window(
        btc_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS
    )
    sealed_pairs = split_pairs_by_window(
        btc_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS
    )

    base_pairs = v22_pairs(btc, cfg_v22, warmup)
    base_val = replay_metrics(
        split_pairs_by_window(
            base_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS
        ),
        cfg_v22,
    )
    base_sealed = replay_metrics(
        split_pairs_by_window(
            base_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS
        ),
        cfg_v22,
    )

    gate1 = gate1_validation(val_pairs, base_val)
    gate2 = gate3 = None
    if not gate1["passed"]:
        verdict = "CLOSED_NEGATIVE_VALIDATION"
    else:
        gate2 = gate2_sealed(sealed_pairs, base_sealed)
        if not gate2["passed"]:
            verdict = "CLOSED_NEGATIVE_SEALED_BTC"
        else:
            eth_pairs = split_pairs_by_window(
                v3_stream(eth, cfg_fit, fitted_matrix, cfg_v22, lookback),
                SEALED_START_TS_MS + PURGE_MS,
                SPAN_END_TS_MS,
            )
            sol_pairs = split_pairs_by_window(
                v3_stream(sol, cfg_fit, fitted_matrix, cfg_v22, lookback),
                SEALED_START_TS_MS + PURGE_MS,
                SPAN_END_TS_MS,
            )
            gate3 = gate3_transfer(eth_pairs, sol_pairs)
            verdict = (
                "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
                if gate3["passed"]
                else "CLOSED_NEGATIVE_TRANSFER"
            )

    return {
        "engine_hash_v3": engine_hash_v3(cfg_v3),
        "label": EVAL_LABEL,
        "data": {
            "btc_candles": len(btc),
            "eth_candles": len(eth),
            "sol_candles": len(sol),
            "btc_fingerprint": series_fingerprint(btc),
        },
        "frozen_constants": {
            "span_start_ts_ms": SPAN_START_TS_MS,
            "train_end_ts_ms": TRAIN_END_TS_MS,
            "sealed_start_ts_ms": SEALED_START_TS_MS,
            "span_end_ts_ms": SPAN_END_TS_MS,
            "purge_ms": PURGE_MS,
            "effective_trials": EFFECTIVE_TRIALS,
            "ci_lo_q": CI_LO_Q,
            "panel_floor": PANEL_FLOOR,
            "bracket": {
                "k_stop": K_STOP,
                "k_trail": K_TRAIL,
                "max_bars": MAX_BARS,
                "atr_period": ATR_PERIOD,
            },
        },
        "segments": {"train": len(train)},
        "fitted": {
            "q_floors": q_floors,
            "matrix": fitted_matrix_payload(fitted_matrix),
            "effective_trials": EFFECTIVE_TRIALS,
        },
        "baseline_v22": {"validation": base_val, "sealed": base_sealed},
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "verdict": verdict,
    }
