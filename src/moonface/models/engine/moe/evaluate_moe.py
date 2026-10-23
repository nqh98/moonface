from __future__ import annotations

import random

from moonface.core.bundle import DataBundle
from moonface.core.metrics import _kurtosis, _sharpe, _skew, deflated_sharpe
from moonface.core.risk import atr
from moonface.models.engine.moe.combiner import decide_moe
from moonface.models.engine.moe.config_moe import identity_hash, moe_hash
from moonface.models.engine.moe.experts import (
    ORTHO_CONSTANTS,
    ExpertContext,
    OI_LOOKBACK,
    default_experts,
    raw_value,
)
from moonface.models.engine.moe.normalize import Normalizer
from moonface.models.engine.moe.nulls import iid_shuffle, phase_randomize, sign_flip
from moonface.models.engine.moe.power import allowed_p_eff, check_power_budget
from moonface.models.engine.moe.regimes import MoeRegime, classify_moe_regime
from moonface.models.engine.moe.weights import EdgeSample, fit_weights, p_eff
from moonface.models.engine.repair import block_ci_q, replay_metrics
from moonface.models.engine.v3.evaluate import (
    CI_HI_Q,
    CI_LO_Q,
    LOOKBACK,
    PURGE_MS,
    SEALED_START_TS_MS,
    SPAN_END_TS_MS,
    TRAIN_END_TS_MS,
    V3Trade,
    gate1_validation,
    gate2_sealed,
    gate3_transfer,
    simulate_bracket_v3,
    split_pairs_by_window,
    v22_pairs,
)

EFFECTIVE_TRIALS = 12


def _regime_at(candles, i, cfg_v3, lookback):
    window = candles[max(0, i - lookback + 1) : i + 1]
    return classify_moe_regime(window, cfg_v3), window


def _raw_series(candles, cfg_v3, experts, lookback, funding=None, oi=None):
    bars = list(range(min(lookback, len(candles)), len(candles)))
    series = {expert.name: [] for expert in experts}
    regimes = []
    for i in bars:
        regime_start = max(0, i - lookback + 1)
        regimes.append(classify_moe_regime(candles[regime_start : i + 1], cfg_v3))
        ctx = ExpertContext(
            window=candles[regime_start : i + 1],
            index=i - regime_start,
            cfg=cfg_v3,
            funding=(funding[regime_start : i + 1] if funding is not None else None),
            oi=(oi[regime_start : i + 1] if oi is not None else None),
        )
        for expert in experts:
            expert_ctx = ctx
            if expert.name == "OI" and ctx.index < OI_LOOKBACK:
                oi_start = max(0, i - OI_LOOKBACK)
                expert_ctx = ExpertContext(
                    window=candles[oi_start : i + 1],
                    index=i - oi_start,
                    cfg=cfg_v3,
                    funding=(funding[oi_start : i + 1] if funding is not None else None),
                    oi=(oi[oi_start : i + 1] if oi is not None else None),
                )
            series[expert.name].append(raw_value(expert.signal(expert_ctx)))
    return bars, regimes, series


def build_fit_panel(
    candles,
    cfg_v3,
    cfg_v22,
    experts,
    lookback=LOOKBACK,
    end_ts_ms=None,
    funding=None,
    oi=None,
):
    bars, regimes, series = _raw_series(candles, cfg_v3, experts, lookback, funding, oi)
    samples: list[EdgeSample] = []
    train_series: dict[str, list[float]] = {expert.name: [] for expert in experts}
    bracket_cache: dict[tuple[int, int], float | None] = {}

    def bracket_r(i, direction):
        key = (i, direction)
        if key not in bracket_cache:
            trade = simulate_bracket_v3(candles, i, direction, 0.5, "MOE", "fit", cfg_v22)
            bracket_cache[key] = trade.net_r if trade is not None else None
        return bracket_cache[key]

    for pos, i in enumerate(bars):
        if end_ts_ms is not None and candles[i].timestamp_ms >= end_ts_ms:
            continue
        regime = regimes[pos]
        for expert in experts:
            train_series[expert.name].append(series[expert.name][pos])
        if regime == MoeRegime.FLAT:
            continue
        for expert in experts:
            raw = series[expert.name][pos]
            direction = 1 if raw > 0 else -1 if raw < 0 else 0
            if direction == 0:
                continue
            net_r = bracket_r(i, direction)
            if net_r is None:
                continue
            samples.append(EdgeSample(regime, expert.name, direction, net_r))
    return samples, train_series


def moe_stream(
    candles,
    cfg_v3,
    cfg_v22,
    experts,
    normalizer,
    W,
    cfg_moe,
    lookback=LOOKBACK,
    funding=None,
    oi=None,
):
    bars, _regimes, series = _raw_series(candles, cfg_v3, experts, lookback, funding, oi)
    return _stream_from_series(candles, cfg_v3, cfg_v22, experts, bars, series, normalizer, W, cfg_moe, lookback)


def dsr_of_pairs(pairs, n_trials=EFFECTIVE_TRIALS) -> float:
    rs = [trade.net_r for trade, _ in pairs]
    if len(rs) < 2:
        return 0.0
    sr = _sharpe(rs)
    return deflated_sharpe(sr, len(rs), _skew(rs), _kurtosis(rs), [sr], n_trials)


def _validation_ci_positive(pairs) -> bool:
    val = split_pairs_by_window(pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS)
    if len(val) < 2:
        return False
    ci = block_ci_q(
        val,
        lambda pair: pair[0].entry_index,
        lambda rows: (sum(trade.net_r for trade, _ in rows) / len(rows)) if rows else 0.0,
        CI_LO_Q,
        CI_HI_Q,
    )
    return ci is not None and ci[0] > 0.0


def _fit_from_series(candles, cfg_v3, cfg_v22, experts, series, cfg_moe, lookback):
    bars = list(range(min(lookback, len(candles)), len(candles)))
    train_bar_set = {i for i in bars if candles[i].timestamp_ms < TRAIN_END_TS_MS}
    train_series = {
        name: [series[name][pos] for pos, i in enumerate(bars) if i in train_bar_set]
        for name in series
    }
    normalizer = Normalizer.fit(train_series, cfg_moe)
    samples: list[EdgeSample] = []
    bracket_cache: dict[tuple[int, int], float | None] = {}

    def bracket_r(i, direction):
        key = (i, direction)
        if key not in bracket_cache:
            trade = simulate_bracket_v3(candles, i, direction, 0.5, "MOE", "fit", cfg_v22)
            bracket_cache[key] = trade.net_r if trade is not None else None
        return bracket_cache[key]

    for pos, i in enumerate(bars):
        if candles[i].timestamp_ms >= TRAIN_END_TS_MS:
            continue
        regime, _window = _regime_at(candles, i, cfg_v3, lookback)
        if regime == MoeRegime.FLAT:
            continue
        for expert in experts:
            raw = series[expert.name][pos]
            direction = 1 if raw > 0 else -1 if raw < 0 else 0
            if direction == 0:
                continue
            net_r = bracket_r(i, direction)
            if net_r is None:
                continue
            samples.append(EdgeSample(regime, expert.name, direction, net_r))
    names = [expert.name for expert in experts]
    W = fit_weights(samples, names, cfg_moe, n_train_trades=len(samples))
    return normalizer, W, samples


def null_calibration(candles, cfg_v3, cfg_v22, experts, cfg_moe, funding=None, oi=None) -> dict:
    bars, _regimes, series = _raw_series(candles, cfg_v3, experts, LOOKBACK, funding, oi)
    generators = {
        "iid_shuffle": iid_shuffle,
        "sign_flip": sign_flip,
        "phase_randomize": phase_randomize,
    }
    runs = {}
    passed_negative = True
    for label, generator in generators.items():
        # Independent RNG per generator (seeded from cfg_moe.seed + label): a shared,
        # sequentially-advanced Random would let one generator's entropy draw (which
        # scales with len(experts), including no-fire experts) shift another
        # generator's null draw — coupling results to the expert set for no
        # statistical reason.
        rng = random.Random(f"{cfg_moe.seed}:{label}")
        nulled = generator(series, rng)
        normalizer, W, samples = _fit_from_series(candles, cfg_v3, cfg_v22, experts, nulled, cfg_moe, LOOKBACK)
        pairs = _stream_from_series(candles, cfg_v3, cfg_v22, experts, bars, nulled, normalizer, W, cfg_moe)
        positive = _validation_ci_positive(pairs)
        allowed = allowed_p_eff(len(samples), cfg_moe.m_per_weight)
        eff = p_eff(W)
        budget_ok = eff <= allowed
        runs[label] = {
            "n": len(pairs),
            "p_eff": eff,
            "allowed": allowed,
            "budget_ok": budget_ok,
            "dsr": round(dsr_of_pairs(pairs), 4),
            "validation_ci_positive": positive,
        }
        if positive or not budget_ok:
            passed_negative = False
    return {"passed_negative": passed_negative, "runs": runs}


def _stream_from_series(
    candles,
    cfg_v3,
    cfg_v22,
    experts,
    bars,
    series,
    normalizer,
    W,
    cfg_moe,
    lookback=LOOKBACK,
):
    by_index = {name: dict(zip(bars, values)) for name, values in series.items()}
    pairs: list[tuple[V3Trade, float]] = []
    busy_until = -1
    for i in bars:
        if i <= busy_until:
            continue
        window = candles[max(0, i - lookback + 1) : i + 1]
        regime = classify_moe_regime(window, cfg_v3)
        s_by_expert = {
            expert.name: normalizer.transform(expert.name, by_index[expert.name].get(i, 0.0))
            for expert in experts
        }
        decision = decide_moe(s_by_expert, regime, W, cfg_moe)
        if decision.action != "ENTER":
            continue
        trade = simulate_bracket_v3(
            candles, i, decision.direction, abs(decision.score), "MOE", regime.value, cfg_v22
        )
        if trade is None:
            break
        tail = candles[max(0, i - cfg_v22.atr_period) : i + 1]
        close = candles[i].close
        atr_frac = atr(tail, cfg_v22.atr_period) / close if close > 0 else 0.0
        pairs.append((trade, atr_frac))
        busy_until = trade.exit_index
    return pairs


def _pairs_for_asset(candles, cfg_v3, cfg_v22, experts, normalizer, W, cfg_moe, lookback, funding=None, oi=None):
    bars, _regimes, series = _raw_series(candles, cfg_v3, experts, lookback, funding, oi)
    return _stream_from_series(
        candles,
        cfg_v3,
        cfg_v22,
        experts,
        bars,
        series,
        normalizer,
        W,
        cfg_moe,
        lookback,
    )


def build_moe_report(
    btc,
    eth,
    sol,
    cfg_v3,
    cfg_v22,
    cfg_moe,
    warmup,
    lookback=LOOKBACK,
    experts=None,
):
    if experts is None:
        experts = default_experts()

    def _bundle_parts(bundle_or_candles):
        if isinstance(bundle_or_candles, DataBundle):
            return bundle_or_candles.candles, bundle_or_candles.funding, bundle_or_candles.feature
        return bundle_or_candles, None, None

    btc_candles, btc_funding, btc_oi = _bundle_parts(btc)
    eth_candles, eth_funding, eth_oi = _bundle_parts(eth)
    sol_candles, sol_funding, sol_oi = _bundle_parts(sol)

    gate0 = null_calibration(
        btc_candles,
        cfg_v3,
        cfg_v22,
        experts,
        cfg_moe,
        funding=btc_funding,
        oi=btc_oi,
    )

    train_samples, train_series = build_fit_panel(
        btc_candles,
        cfg_v3,
        cfg_v22,
        experts,
        lookback,
        end_ts_ms=TRAIN_END_TS_MS,
        funding=btc_funding,
        oi=btc_oi,
    )
    normalizer = Normalizer.fit(train_series, cfg_moe)
    names = [expert.name for expert in experts]
    W = fit_weights(train_samples, names, cfg_moe, n_train_trades=len(train_samples))
    eff = p_eff(W)
    allowed = allowed_p_eff(len(train_samples), cfg_moe.m_per_weight)
    power_ok = check_power_budget(len(train_samples), eff, cfg_moe.m_per_weight)

    report = {
        "moe_hash": moe_hash(cfg_moe),
        "identity_hash": identity_hash(cfg_moe, names, ORTHO_CONSTANTS),
        "experts": names,
        "ortho_constants": dict(ORTHO_CONSTANTS),
        "gate0": gate0,
        "power": {
            "n_train": len(train_samples),
            "p_eff": eff,
            "allowed": allowed,
            "passed": power_ok,
        },
        "fitted": {
            "p_eff": eff,
            "matrix": {
                regime.value: {
                    name: round(weight, 4) for name, weight in row.items() if weight > 0.0
                }
                for regime, row in W.items()
            },
        },
        "gate1": None,
        "gate2": None,
        "gate3": None,
    }

    if not gate0["passed_negative"]:
        report["verdict"] = "GATE0_FAILED_HALT"
        return report
    if not power_ok:
        report["verdict"] = "POWER_BUDGET_REFUSED"
        return report

    btc_pairs = _pairs_for_asset(
        btc_candles,
        cfg_v3,
        cfg_v22,
        experts,
        normalizer,
        W,
        cfg_moe,
        lookback,
        funding=btc_funding,
        oi=btc_oi,
    )
    val_pairs = split_pairs_by_window(
        btc_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS
    )
    base_pairs = v22_pairs(btc_candles, cfg_v22, warmup)
    base_val = replay_metrics(
        split_pairs_by_window(base_pairs, TRAIN_END_TS_MS + PURGE_MS, SEALED_START_TS_MS),
        cfg_v22,
    )
    gate1 = gate1_validation(val_pairs, base_val)
    report["gate1"] = gate1
    if not gate1["passed"]:
        report["verdict"] = "CLOSED_NEGATIVE_VALIDATION"
        return report

    sealed_pairs = split_pairs_by_window(
        btc_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS
    )
    base_sealed = replay_metrics(
        split_pairs_by_window(base_pairs, SEALED_START_TS_MS + PURGE_MS, SPAN_END_TS_MS),
        cfg_v22,
    )
    gate2 = gate2_sealed(sealed_pairs, base_sealed)
    report["gate2"] = gate2
    if not gate2["passed"]:
        report["verdict"] = "CLOSED_NEGATIVE_SEALED_BTC"
        return report

    eth_pairs = split_pairs_by_window(
        _pairs_for_asset(
            eth_candles,
            cfg_v3,
            cfg_v22,
            experts,
            normalizer,
            W,
            cfg_moe,
            lookback,
            funding=eth_funding,
            oi=eth_oi,
        ),
        SEALED_START_TS_MS + PURGE_MS,
        SPAN_END_TS_MS,
    )
    sol_pairs = split_pairs_by_window(
        _pairs_for_asset(
            sol_candles,
            cfg_v3,
            cfg_v22,
            experts,
            normalizer,
            W,
            cfg_moe,
            lookback,
            funding=sol_funding,
            oi=sol_oi,
        ),
        SEALED_START_TS_MS + PURGE_MS,
        SPAN_END_TS_MS,
    )
    gate3 = gate3_transfer(eth_pairs, sol_pairs)
    report["gate3"] = gate3
    report["verdict"] = (
        "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
        if gate3["passed"]
        else "CLOSED_NEGATIVE_TRANSFER"
    )
    return report
