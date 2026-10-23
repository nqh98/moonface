"""Post-program participation advisor.

The research program closed negative (experiments/PROGRAM_CONCLUSION.md): no
OOS-valid edge exists on free BTC data, so this advisor makes NO expectancy
claim. It implements the evidence-bounded fallback framework instead:

- Layer 0: WAIT is the structural default.
- Layer 1: H4 donchian_break up-state is the only participation condition —
  the most replicated positive fixed-horizon drift the program observed.
- Layer 2: LONG only (no study ever produced short-side evidence); the exit
  is a fixed time horizon, the one exit shape that preserved the drift.
- Layer 3: risk lives entirely in position size. The loader rejects any
  policy whose risk_fraction maps the worst observed unstopped research
  drawdown (-277R) to more than the account drawdown the human accepted,
  and a journal-backed kill switch halts the advisor permanently when the
  realized forward drawdown crosses that same budget.
- Layer 4: the mandate carries a reconfirmation deadline; past it, new
  entries are blocked until the human re-runs the validation harness and
  commits a new date. Signal-shape changes require a new pre-registered
  study through the promotion path, never an edit here.

Participation is an explicit human mandate (the policy file), not a
validated strategy: enabled=false or a missing/invalid file means WAIT.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.core.models import Candle
from moonface.core.bundle import DataBundle
from moonface.core.signal_types import Signal, sentinel_extended, wait
from moonface.research.entries import generate_entries

# Worst unstopped research drawdown observed across every family and both
# timeframes (experiments/PROGRAM_CONCLUSION.md: -100R to -277R). The sizing
# arithmetic and the kill switch are both anchored to it.
WORST_OBSERVED_DRAWDOWN_R = 277.0

_FAMILY = "donchian_break"      # evidence is H4 donchian only; pinned
_TIMEFRAME = "4h"
_DAY_MS = 86_400_000


@dataclass(frozen=True)
class ParticipationPolicy:
    """The human participation mandate. Editing this file is the only way to
    enable, size, reconfirm, or (after a kill) revive the advisor."""

    enabled: bool
    donchian_n: int
    horizon_bars: int
    atr_period: int
    risk_fraction: float            # account fraction risked per 1R (ATR)
    max_account_drawdown: float     # accepted account DD; anchors the kill switch
    reconfirm_by: str               # ISO date; past it, new entries are blocked
    asset: dict                     # {"exchange","symbol","timeframe"}
    provenance: dict = field(default_factory=dict)


def _reconfirm_deadline_ms(reconfirm_by: str) -> int:
    """Mandate is valid through the end (UTC) of the reconfirm_by date."""
    d = date.fromisoformat(reconfirm_by)
    midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(midnight.timestamp() * 1000) + _DAY_MS


def load_policy(path: str | Path) -> ParticipationPolicy | None:
    """Fail-safe loader: missing file, parse error, or schema violation all
    return None — the CLI then behaves as if no mandate exists."""
    try:
        raw = json.loads(Path(path).read_text())
        p = ParticipationPolicy(**raw)
        _reconfirm_deadline_ms(p.reconfirm_by)
    except (OSError, ValueError, TypeError):
        return None
    if (not isinstance(p.enabled, bool)
            or not isinstance(p.donchian_n, int) or p.donchian_n <= 0
            or not isinstance(p.horizon_bars, int) or p.horizon_bars <= 0
            or not isinstance(p.atr_period, int) or p.atr_period <= 0
            or not isinstance(p.risk_fraction, (int, float))
            or p.risk_fraction <= 0
            or not isinstance(p.max_account_drawdown, (int, float))
            or not 0 < p.max_account_drawdown < 1
            or p.risk_fraction * WORST_OBSERVED_DRAWDOWN_R
            > p.max_account_drawdown
            or not isinstance(p.asset, dict)
            or p.asset.get("timeframe") != _TIMEFRAME):
        return None
    return p


def policy_hash(p: ParticipationPolicy) -> str:
    """Identity of the risk-relevant content. enabled/reconfirm_by/provenance
    are excluded so mandate flips and routine reconfirmations neither start a
    new journal segment nor reset kill-switch memory."""
    payload = {"donchian_n": p.donchian_n, "horizon_bars": p.horizon_bars,
               "atr_period": p.atr_period, "risk_fraction": p.risk_fraction,
               "max_account_drawdown": p.max_account_drawdown,
               "asset": p.asset}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def realized_drawdown_r(p: ParticipationPolicy, entries: list[dict],
                        candles: list[Candle]) -> float:
    """Max peak-to-trough drawdown (in R, positive magnitude) of the journaled
    forward trades, scored by the same horizon_hold math the research ladder
    used. Trades whose horizon has not resolved inside the candle window are
    skipped — the open-position guard handles the live one."""
    from moonface.research.ladder import single_trade_r

    version = policy_hash(p)
    index_by_ts = {c.timestamp_ms: i for i, c in enumerate(candles)}
    exit_params = {"n_bars": p.horizon_bars, "atr_period": p.atr_period}
    cum = peak = worst = 0.0
    for e in entries:
        if (e.get("strategy_version") != version
                or e.get("decision") != "LONG"):
            continue
        i = index_by_ts.get(e.get("candle_ts_ms"))
        if i is None or i + p.horizon_bars > len(candles) - 1:
            continue
        res = single_trade_r(candles, i, "LONG", "horizon_hold", exit_params)
        if res is None:
            continue
        cum += res[0]
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def _kill(reason: str) -> Signal:
    return Signal("WAIT", None, None, None, reason, kill_switch=True)


def evaluate_participation(p: ParticipationPolicy, candles: list[Candle],
                           entries: list[dict], now_ms: int) -> Signal:
    """The WAIT-default decision ladder for the last closed candle."""
    if not p.enabled:
        return wait("participation not mandated (policy disabled)")
    if len(candles) < p.donchian_n + 2:
        return wait("not enough closed candles for the donchian window")

    version = policy_hash(p)
    mine = [e for e in entries if e.get("strategy_version") == version]
    if any(e.get("kill_switch") for e in mine):
        return _kill("kill switch fired previously — flat pending human"
                     " review (new policy version required)")
    dd_r = realized_drawdown_r(p, mine, candles)
    if dd_r * p.risk_fraction >= p.max_account_drawdown:
        return _kill(f"kill switch: realized forward drawdown {dd_r:.1f}R x"
                     f" f={p.risk_fraction} breaches the"
                     f" {p.max_account_drawdown:.1%} account budget — flatten;"
                     " human review required")

    tf_ms = TIMEFRAME_MS[p.asset["timeframe"]]
    last_ts = candles[-1].timestamp_ms
    longs = [e for e in mine if e.get("decision") == "LONG"
             and isinstance(e.get("candle_ts_ms"), int)]
    if longs:
        bars_held = (last_ts - longs[-1]["candle_ts_ms"]) // tf_ms
        if 0 <= bars_held < p.horizon_bars:
            return wait(f"position open (bar {bars_held}/{p.horizon_bars}"
                         " of the time horizon)")
        if bars_held == p.horizon_bars:
            return wait(f"horizon expired after {p.horizon_bars} bars —"
                         " flatten at this close")

    if now_ms >= _reconfirm_deadline_ms(p.reconfirm_by):
        return wait(f"reconfirmation overdue (mandate lapsed"
                     f" {p.reconfirm_by}) — re-run the validation harness")

    last_index = len(candles) - 1
    extended = sentinel_extended(DataBundle(candles=list(candles)))
    sides = [side for i, side in
             generate_entries(_FAMILY, {"n": p.donchian_n}, extended)
             if i == last_index]
    if not sides:
        return wait("no donchian up-state break on the last closed candle")
    if sides[-1] != "LONG":
        return wait("donchian break is downward — no short-side evidence"
                     " exists; staying flat")
    return Signal("LONG", candles[last_index].close, None, p.risk_fraction,
                  f"{_FAMILY} n={p.donchian_n} up-state break; time exit"
                  f" after {p.horizon_bars} bars, no price stop"
                  " (participation framework, no expectancy claim)")
