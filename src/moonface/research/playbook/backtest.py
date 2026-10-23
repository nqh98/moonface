from __future__ import annotations

from dataclasses import dataclass

from moonface.core.metrics import single_trade_r
from moonface.core.risk import atr, risk_unit
from moonface.research.playbook.config import (LONG_SIGNAL, WAIT,
                                               NO_TRADE, DOWNTREND, INVALID)
from moonface.research.playbook.engine import evaluate_bar
from moonface.research.playbook.journal import JournalEvent
from moonface.research.playbook.regime import classify_regime


@dataclass(frozen=True)
class Trade:
    entry_index: int
    exit_name: str
    exit_params: dict
    final_r: float
    mae_r: float
    mfe_r: float
    outcome_class: str


def _excursions(view, i, hold_cap, atr_period):
    unit = risk_unit(view.h1, i, 1.0, atr_period)
    if unit is None or unit <= 0:
        return 0.0, 0.0
    entry = view.h1[i].close
    end = min(i + hold_cap, len(view.h1) - 1)
    mae = mfe = 0.0
    for j in range(i + 1, end + 1):
        mae = min(mae, (view.h1[j].low - entry) / unit)
        mfe = max(mfe, (view.h1[j].high - entry) / unit)
    return round(mae, 4), round(mfe, 4)


def _regime_breaks(view, i, hold_cap, params):
    end = min(i + hold_cap, len(view.h1) - 1)
    for j in range(i + 1, end + 1):
        if classify_regime(view.h4_prefix(j), params) in (NO_TRADE, DOWNTREND):
            return True
    return False


def replay(view, config) -> tuple[list[Trade], list[JournalEvent]]:
    params, exit_name, exit_params = config.params, config.exit_name, config.exit_params
    hold_cap = exit_params.get("max_bars") or exit_params.get("n_bars") or 96
    trades: list[Trade] = []
    journal: list[JournalEvent] = []
    in_pos_until = -1
    counter = 0
    for i in range(len(view.h1)):
        if i <= in_pos_until:
            continue
        st = evaluate_bar(view, i, params, exit_name, exit_params)
        if st.status == WAIT:
            continue
        counter += 1
        jid = f"PB-{i}-{counter}"
        a = atr(view.h1[: i + 1], params.atr_period)
        ev = JournalEvent(
            journal_id=jid, timestamp_ms=view.h1[i].timestamp_ms, status=st.status,
            regime=st.regime, setup=st.setup, confirm_2h=st.confidence >= 0.5,
            indicators={"atr": round(a, 4), "confidence": st.confidence},
            entry=st.entry, stop=st.stop, exit_rule=exit_name, risk_r=st.risk_r,
            reason=st.reason, invalidation_reason=None, final_r=None, mae_r=None,
            mfe_r=None, outcome_class=None)
        if st.status != LONG_SIGNAL:
            journal.append(ev)
            continue
        res = single_trade_r(view.h1, i, "LONG", exit_name, exit_params)
        if res is None:
            ev.status = INVALID
            ev.invalidation_reason = "untradeable entry (insufficient forward bars)"
            journal.append(ev)
            continue
        final_r = res[0]
        mae, mfe = _excursions(view, i, hold_cap, params.atr_period)
        if _regime_breaks(view, i, hold_cap, params):
            outcome = "failed_by_regime"
        elif "late_extended" in st.reason:
            outcome = "late"
        elif final_r > 0:
            outcome = "clean"
        else:
            outcome = "choppy"
        ev.final_r, ev.mae_r, ev.mfe_r, ev.outcome_class = (round(final_r, 4),
                                                            mae, mfe, outcome)
        journal.append(ev)
        trades.append(Trade(i, exit_name, dict(exit_params), round(final_r, 4),
                            mae, mfe, outcome))
        in_pos_until = min(i + hold_cap, len(view.h1) - 1)
    return trades, journal


def playbook_trade_rs(view, config) -> list[float]:
    trades, _ = replay(view, config)
    return [t.final_r for t in trades]
