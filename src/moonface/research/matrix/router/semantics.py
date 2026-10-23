from __future__ import annotations

ENTROPY_FREEZE = 0.90
MODE_TREND = 1
MODE_QUARANTINE = 2
MODE_FREEZE = 3
QUARANTINE_SIZE = 0.25
MODE_SIZE: dict[int, float] = {
    MODE_TREND: 1.0,
    MODE_QUARANTINE: QUARANTINE_SIZE,
    MODE_FREEZE: 0.0,
}


def rank_modes(state_scores: dict[int, float | None], k: int) -> dict[int, int]:
    """Rank train-only regime scores into execution modes."""
    modes: dict[int, int] = {state: MODE_FREEZE for state in range(k)}
    defined = sorted(
        (
            (score, state)
            for state in range(k)
            if (score := state_scores.get(state)) is not None
        ),
        key=lambda item: (-item[0], item[1]),
    )
    if not defined:
        return modes
    ordered = [state for _, state in defined]
    modes[ordered[0]] = MODE_TREND
    if len(ordered) > 1:
        modes[ordered[-1]] = MODE_FREEZE
        for state in ordered[1:-1]:
            modes[state] = MODE_QUARANTINE
    return modes


def apply_entropy_override(
    mode: int,
    entropy: float,
    threshold: float = ENTROPY_FREEZE,
) -> int:
    """Freeze bars whose posterior entropy exceeds the configured threshold."""
    return MODE_FREEZE if entropy > threshold else mode
