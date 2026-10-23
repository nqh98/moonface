from __future__ import annotations

from moonface.research.breadth_internal.grid import SignalSpec, all_specs

DISCOVERY_SLICE: tuple[int, int] = (0, 20)
GATED_SLICES: tuple[tuple[int, int], ...] = ((20, 40), (40, 60))
BLOCK_LEN: int = 20
K: int = len(GATED_SLICES)


def net_new_highs_spec() -> SignalSpec:
    """Read-only fetch of the byte-frozen net_new_highs spec from the
    breadth_internal grid. This lane never redefines or tunes it."""
    for spec in all_specs():
        if spec.key == "net_new_highs":
            return spec
    raise LookupError("net_new_highs spec missing from breadth_internal grid")
