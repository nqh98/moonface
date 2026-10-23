"""Step A - AI regime router (Slice 1). Read-only floor comparison."""

from moonface.research.matrix.router.modes import build_bar_modes
from moonface.research.matrix.router.semantics import (
    ENTROPY_FREEZE,
    MODE_FREEZE,
    MODE_QUARANTINE,
    MODE_SIZE,
    MODE_TREND,
    apply_entropy_override,
    rank_modes,
)
from moonface.research.matrix.router.strategy import router_conditioned

__all__ = [
    "ENTROPY_FREEZE",
    "MODE_FREEZE",
    "MODE_QUARANTINE",
    "MODE_SIZE",
    "MODE_TREND",
    "apply_entropy_override",
    "rank_modes",
    "build_bar_modes",
    "router_conditioned",
]
