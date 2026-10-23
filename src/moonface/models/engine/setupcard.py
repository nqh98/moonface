# src/moonface/signal/engine/setupcard.py
"""Human-facing boxed presentation of an engine decision. Pure presentation:
this module reads Decision/ModuleScore/CardPlan and formats text — it never
computes a decision, never journals, never fetches. stdlib only."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.models.engine.confluence import Decision
from moonface.models.engine.engine import NO_CLAIM

# Fixed inner content width. Widened past the 60-char default only if needed
# to fit the NO_CLAIM banner verbatim (it must never be truncated).
_WIDTH = max(60, len(NO_CLAIM) + 4)
_DIRECTION_WORD = {1: "LONG", -1: "SHORT", 0: "—"}


@dataclass(frozen=True)
class CardPlan:
    action: str            # res.action: "OPEN"|"HOLD"|"EXIT"|"WAIT"
    direction: int         # +1 long / -1 short / 0
    entry: float | None
    stop: float | None
    target: float | None
    fraction: float | None
    profile: str | None    # "WT"|"CT"|None
    tier: str | None       # "A"|"B"|None


def _num(x: float | None) -> str:
    return "—" if x is None else str(x)


def _clip(text: str, width: int = _WIDTH - 2) -> str:
    """Truncate a single line to fit the box, so long evidence strings can
    never blow out the fixed-width border or crash rendering."""
    text = text.replace("\n", " ")
    if len(text) <= width:
        return text
    return text[: max(width - 3, 0)] + "..."


def _row(text: str) -> str:
    body = _clip(text)
    return "| " + body.ljust(_WIDTH - 2) + " |"


def _rule(ch: str = "-") -> str:
    return "+" + ch * _WIDTH + "+"


def _module_line(m) -> str:
    sign = "+" if m.direction > 0 else "-" if m.direction < 0 else " "
    contribution = f"{sign}{m.points}" if m.direction != 0 else "0"
    marker = " [no data]" if not m.data_ok else ""
    evidence = "; ".join(m.evidence)
    tail = f" ({evidence})" if evidence else ""
    return f"{m.module}: {contribution} [{m.archetype}]{marker}{tail}"


def _decision_lines(decision: Decision) -> list[str]:
    direction_word = _DIRECTION_WORD.get(decision.direction, "—")
    archetype = decision.archetype or "—"
    policy = decision.policy or "—"
    tier = decision.tier or "—"
    lines = [
        _row(f"decision: {decision.action}  archetype={archetype}"
             f" dir={direction_word}"),
        _row(f"score={decision.score}/{decision.max_attainable}"
             f" tier={tier} breadth={decision.breadth} gate={policy}"),
        _row(decision.detail),
    ]
    if decision.veto:
        lines.append(_row(f"VETO: {decision.veto}"
                          f" shadow_score={decision.shadow_score}"))
    return lines


def _plan_lines(plan: CardPlan) -> list[str]:
    lines = [_row(f"plan action: {plan.action}")]
    if plan.action in ("OPEN", "HOLD"):
        lines.append(_row(
            f"entry={_num(plan.entry)} stop={_num(plan.stop)}"
            f" target={_num(plan.target)}"))
        lines.append(_row(
            f"fraction={_num(plan.fraction)} profile={plan.profile or '—'}"
            f" tier={plan.tier or '—'}"))
    return lines


def render(decision: Decision | None, plan: CardPlan,
          discipline_state: str, version: str) -> str:
    """Render a bordered ASCII SetupCard. Never raises — decision may be None
    (pre-decide WAIT / insufficient history)."""
    lines: list[str] = [
        _rule("="),
        _row(f"CONFLUENCE ENGINE v2  [{version[:8]}]"),
        _rule("="),
    ]

    if decision is None:
        lines.append(_row(f"plan action: {plan.action}"))
        lines.append(_row("no decision — insufficient history"))
    else:
        lines.extend(_decision_lines(decision))
        lines.append(_rule())
        for m in decision.modules:
            lines.append(_row(_module_line(m)))
        lines.append(_rule())
        lines.extend(_plan_lines(plan))

    lines.append(_rule())
    lines.append(_row(f"discipline: {discipline_state}"))
    lines.append(_rule())
    lines.append(_row(NO_CLAIM))
    lines.append(_rule("="))
    return "\n".join(lines)
