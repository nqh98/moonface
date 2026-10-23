"""LLM narrative/macro VETO gate — forward-only permission layer (spec §11).

The LLM never decides LONG/SHORT/entries/exits/stops/targets. It emits one of four
permission labels; `combine` turns (quant permission, Donchian action, LLM label)
into a final paper action + reference-size multiplier. Pure, deterministic, tested.
No historical backtest (hindsight-leakage; see spec §11.1).
"""
from __future__ import annotations

LABELS = ("allow", "veto", "reduce_risk", "uncertain")
ACTIONS = ("LONG", "WAIT")
SCHEMA_VERSION = 1

# Tokens forbidden in the audit-only rationale (LLM must not imply a trade call).
_FORBIDDEN_RATIONALE = (
    "long", "short", "buy", "sell", "entry", "exit", "stop", "target",
    "take profit", "price", "tp", "sl",
)


def combine(quant_allow: bool, donchian_action: str, llm_label: str) -> dict:
    """Return {'action': 'LONG'|'WAIT', 'size_mult': float}.

    - veto / uncertain            -> WAIT (deny / abstain-safe)
    - donchian WAIT or not quant_allow -> WAIT
    - reduce_risk + LONG + quant  -> LONG at half reference size
    - allow + LONG + quant        -> LONG at full reference size
    """
    if donchian_action not in ACTIONS:
        raise ValueError(f"donchian_action must be in {ACTIONS}")
    if llm_label not in LABELS:
        raise ValueError(f"llm_label must be in {LABELS}")

    if llm_label in ("veto", "uncertain"):
        return {"action": "WAIT", "size_mult": 0.0}
    if donchian_action != "LONG" or not quant_allow:
        return {"action": "WAIT", "size_mult": 0.0}
    if llm_label == "reduce_risk":
        return {"action": "LONG", "size_mult": 0.5}
    return {"action": "LONG", "size_mult": 1.0}  # allow


def rationale_is_clean(rationale: str) -> bool:
    """Audit guard: rationale must not contain directional/price/stop/target tokens."""
    low = rationale.lower()
    return not any(tok in low for tok in _FORBIDDEN_RATIONALE)
