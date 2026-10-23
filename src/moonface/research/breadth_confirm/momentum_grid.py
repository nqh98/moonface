from __future__ import annotations

from moonface.research.breadth_confirm.grid import (
    DISCOVERY_SLICE,
    GATED_SLICES,
    K,
)
from moonface.research.breadth_internal.grid import SignalSpec
from moonface.research.breadth_internal.hf_grid import hf_specs

# Derived (not tuned), identical to the Lane 2 HF treatment of this signal:
# h / bars_per_day = 48 / 6 = 8 overlapping holds.
MOMENTUM_BLOCK_LEN: int = 8

__all__ = [
    "DISCOVERY_SLICE",
    "GATED_SLICES",
    "K",
    "MOMENTUM_BLOCK_LEN",
    "breadth_momentum_spec",
]


def breadth_momentum_spec() -> SignalSpec:
    """Read-only fetch of the byte-frozen breadth_momentum spec from the Lane 2
    HF grid. This lane never redefines or tunes it; it only confirms it on
    disjoint volume-rank universe slices."""
    for spec in hf_specs():
        if spec.key == "breadth_momentum":
            return spec
    raise LookupError("breadth_momentum spec missing from breadth_internal hf grid")
