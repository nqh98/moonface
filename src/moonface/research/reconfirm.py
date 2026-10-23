"""Multi-timeframe reconfirmation measurement (registration v1).

Frozen re-measurement of the one observation the participation advisor
leans on: donchian up-break fixed-horizon drift, per timeframe, plus the
4h drawdown anchor. Pure: no network, no file I/O, no policy writes.
Parameters are frozen by experiments/reconfirmation/REGISTRATION.md —
changing them here without a new registration version is a protocol
violation, not a refactor.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.research.participation import WORST_OBSERVED_DRAWDOWN_R

DONCHIAN_N = 100
HORIZON_BARS = 24
ATR_PERIOD = 14
RESEARCH_FRACTION = 0.8
MIN_TOTAL_EVENTS = 30
MIN_OOS_EVENTS = 10
TIMEFRAMES = ("1h", "4h", "1d", "1w")
ANCHOR_TIMEFRAME = "4h"


@dataclass(frozen=True)
class TFResult:
    timeframe: str
    bars: int
    last_bar_ts: int
    n_total: int
    n_research: int
    n_oos: int
    research_mean_r: float
    oos_mean_r: float
    net_r: float
    max_drawdown_r: float
    n_fresh: int | None
    fresh_mean_r: float | None


def measure_timeframe(timeframe: str, candles: list[Candle],
                      prev_last_ts: int | None = None) -> TFResult:
    """Frozen measurement for one timeframe. LONG donchian breaks scored by
    the ladder's own horizon_hold math; events whose horizon does not
    resolve inside the window are excluded (kill-switch join rule)."""
    from moonface.research.ladder import single_trade_r

    exit_params = {"n_bars": HORIZON_BARS, "atr_period": ATR_PERIOD}
    entries = generate_entries("donchian_break", {"n": DONCHIAN_N},
                               DataBundle(candles=candles))
    boundary = int(len(candles) * RESEARCH_FRACTION)
    research: list[float] = []
    oos: list[float] = []
    fresh: list[float] = []
    cum = peak = worst = 0.0
    for i, side in entries:
        if side != "LONG" or i + HORIZON_BARS > len(candles) - 1:
            continue
        res = single_trade_r(candles, i, "LONG", "horizon_hold", exit_params)
        if res is None:
            continue
        r = res[0]
        (research if i < boundary else oos).append(r)
        if prev_last_ts is not None and candles[i].timestamp_ms > prev_last_ts:
            fresh.append(r)
        cum += r
        peak = max(peak, cum)
        worst = max(worst, peak - cum)

    def mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    return TFResult(
        timeframe=timeframe,
        bars=len(candles),
        last_bar_ts=candles[-1].timestamp_ms if candles else 0,
        n_total=len(research) + len(oos),
        n_research=len(research),
        n_oos=len(oos),
        research_mean_r=mean(research),
        oos_mean_r=mean(oos),
        net_r=round(sum(research) + sum(oos), 4),
        max_drawdown_r=round(worst, 4),
        n_fresh=len(fresh) if prev_last_ts is not None else None,
        fresh_mean_r=mean(fresh) if prev_last_ts is not None else None,
    )


def verdict(r: TFResult) -> str:
    """Registration v1 verdict rules, evaluated in order."""
    if r.n_total < MIN_TOTAL_EVENTS or r.n_oos < MIN_OOS_EVENTS:
        return "INSUFFICIENT"
    if r.research_mean_r > 0 and r.oos_mean_r > 0:
        return "ALIVE"
    return "DEGRADED"


def anchor_breached(r: TFResult) -> bool:
    """The 4h sizing anchor: the policy loader maps the worst observed
    unstopped drawdown (277R) to the accepted account budget. A window
    drawdown past it means the inequality understates observed risk."""
    return r.max_drawdown_r > WORST_OBSERVED_DRAWDOWN_R


def build_report(results: dict[str, TFResult],
                 meta: dict) -> tuple[str, dict]:
    """(markdown report, JSON-serializable results dict). The markdown ends
    with the pre-committed recommendation; the dict feeds the next run's
    fresh slice via last_bar_ts."""
    from dataclasses import asdict

    anchor = anchor_breached(results[ANCHOR_TIMEFRAME])
    verdicts = {tf: verdict(r) for tf, r in results.items()}
    ok = verdicts[ANCHOR_TIMEFRAME] == "ALIVE" and not anchor
    recommendation = (
        "bump reconfirm_by one quarter (4h ALIVE, anchor intact)" if ok
        else "HUMAN REVIEW — do not bump reconfirm_by; see the"
             " pre-committed actions in REGISTRATION.md")

    lines = [
        "# Multi-timeframe reconfirmation report",
        "",
        f"- Generated: {meta['generated_utc']}",
        f"- Asset: {meta['asset']['symbol']} ({meta['asset']['exchange']})",
        f"- Window: rolling {meta['window_days']} days; registration v1"
        f" (donchian n={DONCHIAN_N}, horizon {HORIZON_BARS} bars,"
        f" ATR {ATR_PERIOD}, LONG only)",
        "",
        "| TF | bars | n | n_oos | research mean R | OOS mean R | net R |"
        " max DD (R) | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for tf in TIMEFRAMES:
        r = results[tf]
        lines.append(
            f"| {tf} | {r.bars} | {r.n_total} | {r.n_oos} |"
            f" {r.research_mean_r} | {r.oos_mean_r} | {r.net_r} |"
            f" {r.max_drawdown_r} | {verdicts[tf]} |")
    lines += [
        "",
        "- 4h sizing anchor (277R): "
        + ("**ANCHOR BREACHED** — the policy loader inequality understates"
           " observed risk" if anchor else "intact"),
    ]
    fresh = [f"  - {tf}: n={r.n_fresh}, mean R={r.fresh_mean_r}"
             for tf, r in results.items() if r.n_fresh is not None]
    if fresh:
        lines += ["- Since last run (descriptive, no verdict):"] + fresh
    lines += ["", f"**Recommendation:** {recommendation}", ""]

    data = {
        **meta,
        "registration": "v1",
        "anchor_breached": anchor,
        "recommendation": recommendation,
        "timeframes": {tf: {**asdict(r), "verdict": verdicts[tf]}
                       for tf, r in results.items()},
    }
    return "\n".join(lines), data
