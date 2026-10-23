from __future__ import annotations

from dataclasses import dataclass

from moonface.research.playbook.config import (PlaybookParams, SUPPORTIVE, WAIT,
                                               WATCH, LONG_SETUP, LONG_SIGNAL)
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.quality import quality_check
from moonface.research.playbook.regime import classify_regime
from moonface.research.playbook.risk import build_risk_plan
from moonface.research.playbook.setups import detect_setup, two_h_confirms, TRIGGERED

PLAYBOOK_NAME = "BTC Multi-Timeframe Trend Playbook"


@dataclass(frozen=True)
class PlaybookState:
    status: str
    playbook: str
    regime: str
    setup: str | None
    reason: str
    entry: float | None
    stop: float | None
    exit_rule: str
    risk_r: float | None
    confidence: float
    journal_id: str | None = None


def evaluate_bar(view: MTFView, i: int, params: PlaybookParams, exit_name: str,
                 exit_params: dict) -> PlaybookState:
    h1_prefix = view.h1[: i + 1]
    regime = classify_regime(view.h4_prefix(i), params)
    supportive = regime in SUPPORTIVE
    if not supportive:
        return PlaybookState(WAIT, PLAYBOOK_NAME, regime, None,
                             f"regime {regime} not long-supportive", None, None,
                             exit_name, None, 0.0)
    h2_prefix = view.h2_prefix(i)
    setup = detect_setup(h1_prefix, h2_prefix, regime, params)
    if setup is None:
        return PlaybookState(WATCH, PLAYBOOK_NAME, regime, None,
                             "supportive regime, no setup forming", None, None,
                             exit_name, None, 0.3)
    confirm = two_h_confirms(h2_prefix, params)
    q = quality_check(h1_prefix, setup, regime, params)
    triggered = setup.phase == TRIGGERED
    confidence = round(0.3 + 0.2 * confirm + 0.3 * q.passed + 0.2 * triggered, 3)
    plan = build_risk_plan(h1_prefix, setup, params, exit_name, exit_params)
    if triggered and q.passed and confirm:
        return PlaybookState(LONG_SIGNAL, PLAYBOOK_NAME, regime, setup.name,
                             f"{setup.name} triggered, quality+2h confirm",
                             plan.entry, plan.stop, exit_name, plan.initial_r,
                             confidence)
    reason = ("quality: " + ",".join(q.reasons)) if q.reasons else (
        "trigger not confirmed" if not confirm else "setup forming")
    return PlaybookState(LONG_SETUP, PLAYBOOK_NAME, regime, setup.name, reason,
                         plan.entry, plan.stop, exit_name, plan.initial_r,
                         confidence)
