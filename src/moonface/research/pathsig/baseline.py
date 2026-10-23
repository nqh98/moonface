"""Rung-0 baseline: replay existing signal families through the path-signal
harness on the real BTC Sample grid.

Per fold, an empirical signal-frame Distribution is fitted from train-fold
labels only, then applied to fired test bars via the shared decide() policy and
scored by the shared dual-frame evaluate_strategy(). Everything is kept in the
signal's own direction by mirroring SHORT labels, so decide()'s LONG means
"go with the signal" and the LONG-frame realized R stays correct. Design frozen
in docs/research-log/specs/2026-06-16-pathsig-rung0-baseline-design.md."""
from __future__ import annotations

from statistics import fmean

from moonface.core.bundle import DataBundle
from moonface.research.entries import UnknownEntryFamily, generate_entries
from moonface.research.pathsig.data import build_btc_dataset
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Distribution, decide
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds


def _mirror(label: PathLabel, side: str) -> PathLabel:
    """Reframe a LONG-frame label into the signal's own direction. For SHORT
    the adverse/favourable excursions swap and negate (mae stays <=0, mfe >=0)."""
    if side == "SHORT":
        return PathLabel(ret_r=-label.ret_r, mae_r=-label.mfe_r,
                         mfe_r=-label.mae_r)
    return label


def fit_distribution(samples: list[Sample], fire: dict[int, str],
                     positions: list[int], min_events: int
                     ) -> Distribution | None:
    """Mean signal-frame distribution over fired samples at `positions`
    (sample positions, not candle indices). None if fewer than min_events."""
    obs: list[PathLabel] = []
    for pos in positions:
        s = samples[pos]
        side = fire.get(s.index)
        if side is not None:
            obs.append(_mirror(s.label, side))
    if len(obs) < min_events:
        return None
    n = len(obs)
    return Distribution(
        p_up=sum(1 for lbl in obs if lbl.ret_r > 0) / n,
        exp_ret_r=fmean(lbl.ret_r for lbl in obs),
        exp_mae_r=fmean(lbl.mae_r for lbl in obs),
        exp_mfe_r=fmean(lbl.mfe_r for lbl in obs))


# Uniform rung-0 policy constants (no per-signal tuning — that is rung 2's job).
EDGE_THRESHOLD = 0.15
KELLY_SCALE = 0.02
MAX_FRACTION = 0.02
TAKER_BPS = 5.0
SLIPPAGE_BPS = 2.0
MIN_FIT_EVENTS = 10
DRAWDOWN_CAP_R = 15.0

# The 16-asset 4h pool (cross-sectional inputs only; BTC is the deploy target).
POOL_SYMBOLS = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
                "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
                "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
                "ARBUSDT", "AVAXUSDT", "ETCUSDT"]

# Metrics field each positioning family needs on the bundle for generate_entries.
_METRICS_FIELD = {
    "oi_build_momentum": "sum_open_interest",
    "oi_flush_reversal": "sum_open_interest",
    "toptrader_follow": "sum_toptrader_long_short_ratio",
    "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
}

# The frozen signal/param set replayed as the baseline (price + funding +
# positioning + orderbook). Horizon-independent; the label horizon is set per run.
SIGNALS = [
    {"family": "donchian_break", "params": {"n": 100}},
    {"family": "donchian_break", "params": {"n": 55}},
    {"family": "atr_channel_break", "params": {"k": 1.5, "atr_period": 14}},
    {"family": "atr_channel_break", "params": {"k": 2.0, "atr_period": 14}},
    {"family": "ma_cross", "params": {"fast": 50, "slow": 200}},
    {"family": "roc_sign", "params": {"period": 24}},
    {"family": "price_vs_ma", "params": {"period": 100}},
    {"family": "funding_fade", "params": {"window": 60, "z_thr": 1.5}},
    {"family": "funding_confirm", "params": {"persist": 6, "lvl": 0.0003}},
    {"family": "funding_flip", "params": {"debounce": 6}},
    {"family": "oi_build_momentum", "params": {"window": 180, "lookback": 6, "z_thr": 1.5}},
    {"family": "oi_flush_reversal", "params": {"window": 180, "lookback": 6, "z_thr": 1.5}},
    {"family": "toptrader_follow", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "taker_flow_momentum", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 2.0}},
]


def replay_fired(fire: dict[int, str], samples: list[Sample],
                 folds: list[Fold], *, h: int, edge_threshold: float,
                 kelly_scale: float, max_fraction: float, taker_bps: float,
                 slippage_bps: float, min_events: int, n_trials: int,
                 drawdown_cap_r: float) -> dict:
    """Fold loop over a known fire-map. Per fold: fit on train, decide on fired
    test bars, then score the concatenated stream under both risk frames."""
    atr_idx = FEATURE_NAMES.index("atr_frac")
    decisions, labels, atr_fracs, fundings = [], [], [], []
    used_folds = 0
    for fold in folds:
        dist = fit_distribution(samples, fire, fold.train_idx, min_events)
        if dist is None:
            continue
        used_folds += 1
        for pos in fold.test_idx:
            s = samples[pos]
            side = fire.get(s.index)
            if side is None:
                continue
            decisions.append(decide(dist, edge_threshold, kelly_scale,
                                    max_fraction))
            labels.append(_mirror(s.label, side))
            atr_fracs.append(s.x[atr_idx])
            fundings.append(0.0)

    if not decisions:
        return {"status": "too_few_events", "n_events": len(fire),
                "used_folds": used_folds}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=taker_bps, slippage_bps=slippage_bps,
                            n_trials=n_trials, trial_srs=[],
                            drawdown_cap_r=drawdown_cap_r)
    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    return {"status": "ok", "n_events": len(fire), "n_trades": n_trades,
            "used_folds": used_folds, **res}


def replay_signal(family: str, params: dict, bundle, samples: list[Sample],
                  folds: list[Fold], *, h: int, **kw) -> dict:
    """Resolve the fire-map from the family, then replay it. Reports no_data
    when the bundle lacks the family's required series."""
    head = {"family": family, "params": params, "h": h}
    try:
        events = generate_entries(family, params, bundle)
    except (ValueError, UnknownEntryFamily):
        return {**head, "status": "no_data"}
    fire = {i: side for i, side in events}
    return {**head, **replay_fired(fire, samples, folds, h=h, **kw)}


LOCKBOX_FRACTION = 0.2
ATR_PERIOD = 14


def run_baseline_to_doc(readers: dict, *, n_folds: int, horizons: list[int],
                        pool_symbols: list[str] = POOL_SYMBOLS,
                        deploy: str = "BTCUSDT") -> dict:
    """Build the full rung-0 results document from injectable readers (offline
    testable). One row per signal x horizon, sorted by fixed-cap total_r."""
    n_trials = len(SIGNALS) * len(horizons)
    policy = dict(edge_threshold=EDGE_THRESHOLD, kelly_scale=KELLY_SCALE,
                  max_fraction=MAX_FRACTION, taker_bps=TAKER_BPS,
                  slippage_bps=SLIPPAGE_BPS, min_events=MIN_FIT_EVENTS,
                  n_trials=n_trials, drawdown_cap_r=DRAWDOWN_CAP_R)
    rows: list[dict] = []
    for h in horizons:
        base, samples = build_btc_dataset(readers, h=h, atr_period=ATR_PERIOD,
                                          pool_symbols=pool_symbols,
                                          deploy=deploy)
        folds = walk_forward_folds(len(samples), n_folds=n_folds, embargo=h,
                                   lockbox_fraction=LOCKBOX_FRACTION)
        for spec in SIGNALS:
            family, params = spec["family"], spec["params"]
            field = _METRICS_FIELD.get(family, "sum_open_interest")
            bundle = DataBundle(candles=base.candles, funding=base.funding,
                                feature=readers["metrics"](deploy, field),
                                bookdepth=base.bookdepth)
            rows.append(replay_signal(family, params, bundle, samples, folds,
                                      h=h, **policy))

    rows.sort(key=lambda r: r.get("fixed_cap", {}).get("total_r", float("-inf")),
              reverse=True)
    return {
        "config": {
            "deploy": deploy, "horizons": horizons, "n_folds": n_folds,
            "lockbox_fraction": LOCKBOX_FRACTION, "atr_period": ATR_PERIOD,
            "n_trials": n_trials, "edge_threshold": EDGE_THRESHOLD,
            "kelly_scale": KELLY_SCALE, "max_fraction": MAX_FRACTION,
            "taker_bps": TAKER_BPS, "slippage_bps": SLIPPAGE_BPS,
            "min_fit_events": MIN_FIT_EVENTS, "drawdown_cap_r": DRAWDOWN_CAP_R,
            "pool_symbols": pool_symbols,
        },
        "rows": rows,
    }
