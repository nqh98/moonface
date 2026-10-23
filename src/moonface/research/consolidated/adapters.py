from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from moonface.core.metrics import summarize_r
from moonface.data.series import align_funding
from moonface.research.breadth.evaluate import score_records
from moonface.research.breadth.signals import entries_from_state
from moonface.research.breadth_internal.evaluate import _state as bi_state
from moonface.research.breadth_internal.grid import all_specs as bi_all_specs
from moonface.research.btc_classic.evaluate import cell_entries
from moonface.research.btc_classic.grid import all_specs
from moonface.research.btcspec.families import all_explore_configs as btcspec_configs
from moonface.research.btcspec.families_s2 import all_explore_configs_s2 as btcspec_s2_configs
from moonface.research.donchian_filter.evaluate import base_trades
from moonface.research.donchian_filter.grid import deployed_base
from moonface.research.regime_overlay.evaluate import _overlaid_rt
from moonface.research.regime_overlay.grid import CELLS as OVERLAY_CELLS
from moonface.research.regime_overlay.regime import REGIME_DEFS as RDEFS
from moonface.research.regime_selector.grid import CELLS as SEL_CELLS
from moonface.research.regime_selector.selector import selector_rt
from moonface.research.consolidated.result import AdapterResult
from moonface.research.edge_search import net_trade_rs
from moonface.research.practical.families import all_explore_configs as practical_configs
from moonface.research.ls_tournament.explore import evaluate_config
from moonface.research.ls_tournament.grid import configs_for as ls_configs_for
from moonface.research.playbook.backtest import replay as playbook_replay
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.models.engine.config import load_engine_config
from tools.engine.engine_backtest import replay

if TYPE_CHECKING:
    # RunContext is defined in runner.py (Task 12); guarded so this module
    # imports cleanly before runner exists and avoids a runtime import cycle.
    from moonface.research.consolidated.runner import RunContext

ADAPTERS: dict[str, Callable[[RunContext], list[AdapterResult]]] = {}

EXCLUDED: list[dict] = [
    {"lane": "portfolio",
     "reason": "bar-return position stream; no per-trade R, not comparable on expectancy_r"},
    {"lane": "pathsig",
     "reason": "requires aux series (OI/taker/bpos) outside the shared candles+funding load"},
]


def register(lane):
    def deco(fn):
        ADAPTERS[lane] = fn
        return fn
    return deco


def _last_signal(entries, n_bars):
    for i, side in entries:
        if i == n_bars - 1:
            return side
    return "FLAT"


@register("btc_classic")
def _btc_classic(ctx):
    # ctx.funding is loader-native raw (ts, rate) points; btc_classic's
    # funding_fade consumes per-bar aligned floats, so align once here.
    funding = align_funding(ctx.btc_4h, ctx.funding)
    out = []
    for spec in all_specs():
        entries = cell_entries(ctx.btc_4h, funding, spec)
        records = score_records(ctx.btc_4h, entries, spec.exit_name,
                                dict(spec.exit_params))
        out.append(AdapterResult(
            key=f"btc_classic:{spec.key}", lane="btc_classic", unit="r_trade",
            config=dict(spec.params), config_source="frozen_family",
            exit_name=spec.exit_name,
            current_signal=_last_signal(entries, len(ctx.btc_4h)),
            records=records))
    return out


@register("breadth_internal")
def _breadth_internal(ctx):
    out = []
    for spec in bi_all_specs():
        if not ctx.daily or not ctx.btc_4h:
            records = []
        else:
            state = bi_state(ctx.daily, ctx.btc_4h, spec, ctx.is_member)
            entries = entries_from_state(ctx.btc_4h, state, spec.h)
            records = score_records(
                ctx.btc_4h, entries, spec.exit_name, dict(spec.exit_params),
            )
        out.append(AdapterResult(
            key=f"breadth_internal:{spec.key}", lane="breadth_internal",
            unit="r_trade", config=dict(spec.params),
            config_source="frozen_family", exit_name=spec.exit_name,
            current_signal=_last_signal(entries if ctx.daily and ctx.btc_4h else [],
                                        len(ctx.btc_4h)),
            records=records))
    return out


@register("donchian")
def _donchian(ctx):
    trades = base_trades(ctx.btc_4h, ctx.funding)
    rs = [float(t.r_multiple) for t in trades]
    sig = ("LONG" if trades
           and int(trades[-1].entry_index) == len(ctx.btc_4h) - 1
           else "FLAT")
    base = deployed_base()
    return [AdapterResult(
        key="donchian:deploy_base", lane="donchian", unit="r_trade",
        config={"entry_n": base.entry_n, "trail_n": base.trail_n},
        config_source="deployed", exit_name="donchian_trail",
        current_signal=sig, r_stream=rs)]


def _rt_last_signal(rt: list[tuple[int, float]], last_ts: int) -> str:
    if rt and rt[-1][0] == last_ts:
        return "LONG" if rt[-1][1] >= 0 else "SHORT"
    return "FLAT"


@register("regime_overlay")
def _regime_overlay(ctx):
    rmap = {r.id: r for r in RDEFS}
    best = None
    for c in OVERLAY_CELLS:
        rt = _overlaid_rt(ctx.btc_4h, ctx.funding, deployed_base(),
                          rmap[c.regime_id], ctx.macro, c.mode)
        tot = sum(r for _, r in rt)
        if best is None or tot > best[0]:
            best = (tot, c, rt)
    _, c, rt = best
    last_ts = ctx.btc_4h[-1].timestamp_ms
    return [AdapterResult(
        key=f"regime_overlay:{c.cell_id}", lane="regime_overlay",
        unit="r_trade", config={"regime": c.regime_id, "mode": c.mode},
        config_source="top_explore", exit_name="donchian_trail",
        current_signal=_rt_last_signal(rt, last_ts),
        r_stream=[r for _, r in rt])]


@register("regime_selector")
def _regime_selector(ctx):
    rmap = {r.id: r for r in RDEFS}
    best = None
    for c in SEL_CELLS:
        rt = selector_rt(ctx.btc_4h, ctx.macro, rmap[c.regime_id],
                         c.riskoff_action, 1.0)
        tot = sum(r for _, r in rt)
        if best is None or tot > best[0]:
            best = (tot, c, rt)
    _, c, rt = best
    last_ts = ctx.btc_4h[-1].timestamp_ms
    return [AdapterResult(
        key=f"regime_selector:{c.cell_id}", lane="regime_selector",
        unit="r_trade",
        config={"regime": c.regime_id, "riskoff_action": c.riskoff_action},
        config_source="top_explore", exit_name="donchian_trail",
        current_signal=_rt_last_signal(rt, last_ts),
        r_stream=[r for _, r in rt])]


def _top_by_expectancy(ctx, configs):
    """Evaluate every config on its NATIVE timeframe's candles; return (best_config, best_rs)."""
    tf_candles = {"1h": ctx.btc_1h, "2h": ctx.btc_2h, "4h": ctx.btc_4h}
    best_cfg, best_rs, best_exp = None, [], None
    for cfg in configs:
        candles = tf_candles.get(getattr(cfg, "timeframe", "4h"), ctx.btc_4h)
        rs = net_trade_rs(candles, cfg.family, dict(cfg.params),
                          cfg.exit_name, dict(cfg.exit_params), cfg.h)
        exp = summarize_r(rs).expectancy_r
        if best_exp is None or exp > best_exp:
            best_cfg, best_rs, best_exp = cfg, rs, exp
    return best_cfg, best_rs


@register("practical")
def _practical(ctx):
    cfg, rs = _top_by_expectancy(ctx, practical_configs())
    return [AdapterResult(
        key=f"practical:{cfg.label}", lane="practical", unit="r_trade",
        config=dict(cfg.params), config_source="top_explore",
        exit_name=cfg.exit_name, current_signal="FLAT",
        r_stream=rs)]


@register("btcspec")
def _btcspec(ctx):
    all_cfgs = list(btcspec_configs()) + list(btcspec_s2_configs())
    cfg, rs = _top_by_expectancy(ctx, all_cfgs)
    return [AdapterResult(
        key=f"btcspec:{cfg.label}", lane="btcspec", unit="r_trade",
        config=dict(cfg.params), config_source="top_explore",
        exit_name=cfg.exit_name, current_signal="FLAT",
        r_stream=rs)]


@register("ls_tournament")
def _ls_tournament(ctx):
    context = {"funding": ctx.funding, "macro": ctx.macro, "oi_points": []}
    best_cfg, best_recs, best_exp = None, [], None
    for cfg in ls_configs_for("4h"):
        recs = evaluate_config(ctx.btc_4h, cfg, context)["records"]
        exp = summarize_r([r["net_r"] for r in recs]).expectancy_r
        if best_exp is None or exp > best_exp:
            best_cfg, best_recs, best_exp = cfg, recs, exp
    sig = _last_signal([(r["i"], r["side"]) for r in best_recs], len(ctx.btc_4h))
    return [AdapterResult(
        key=f"ls_tournament:{best_cfg.label}", lane="ls_tournament",
        unit="r_trade",
        config={"label": best_cfg.label, "exit_name": best_cfg.exit_name,
                "h": best_cfg.h,
                "oi_momentum": "inactive (OI not in shared load)"},
        config_source="top_explore", exit_name=best_cfg.exit_name,
        current_signal=sig, records=best_recs)]


@register("playbook")
def _playbook(ctx):
    view = MTFView.build(ctx.btc_1h, ctx.btc_2h, ctx.btc_4h)
    configs = all_playbook_configs()
    config_source = "deployed" if len(configs) == 1 else "top_explore"
    best_cfg, best_rs, best_journal, best_exp = None, [], [], None
    for cfg in configs:
        trades, journal = playbook_replay(view, cfg)
        rs = [float(t.final_r) for t in trades]
        exp = summarize_r(rs).expectancy_r
        if best_exp is None or exp > best_exp:
            best_cfg, best_rs, best_journal, best_exp = cfg, rs, journal, exp
    last_ts = ctx.btc_1h[-1].timestamp_ms if ctx.btc_1h else 0
    sig = ("LONG" if any(
        e.timestamp_ms == last_ts and e.status == "LONG_SIGNAL"
        for e in best_journal) else "FLAT")
    return [AdapterResult(
        key=f"playbook:{best_cfg.label}", lane="playbook", unit="r_trade",
        config={"label": best_cfg.label, "exit_name": best_cfg.exit_name},
        config_source=config_source, exit_name=best_cfg.exit_name,
        current_signal=sig, r_stream=best_rs)]


@register("engine")
def _engine(ctx):
    cfg = load_engine_config("promotion/engine.json")
    entries = replay(cfg, ctx.btc_1h, warmup=400)
    rs = [float(e["realized_r"]) for e in entries if e.get("realized_r") is not None]
    decision = entries[-1]["decision"] if entries else "FLAT"
    sig = decision if decision in ("LONG", "SHORT") else "FLAT"
    return [AdapterResult(
        key="engine:confluence", lane="engine", unit="r_trade",
        config={"config": "promotion/engine.json", "lookback_bars": cfg.lookback_bars,
                "audit": "full-window replay; all-time-DD kill-switch latch not modeled (diverges from forward-faithful read)"},
        config_source="deployed", exit_name="engine",
        current_signal=sig, r_stream=rs)]
