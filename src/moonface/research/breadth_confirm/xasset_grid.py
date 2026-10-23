from __future__ import annotations

from moonface.research.breadth_confirm.momentum_grid import breadth_momentum_spec
from moonface.research.breadth_internal.grid import SignalSpec, all_specs

# Independent traded legs for the transfer test (BTC stays the discovery anchor,
# never re-gated here). SOL futures list ~2020-09, so its window is shorter.
ASSETS: tuple[str, ...] = ("ETHUSDT", "SOLUSDT")


def _net_new_highs_spec() -> SignalSpec:
    for spec in all_specs():
        if spec.key == "net_new_highs":
            return spec
    raise LookupError("net_new_highs spec missing from breadth_internal grid")


def lead_specs() -> list[SignalSpec]:
    """The two never-killed breadth-internal leads, byte-frozen from their home
    grids. This lane only transfers them to ETH/SOL; it never tunes them."""
    return [_net_new_highs_spec(), breadth_momentum_spec()]


# K = (# leads) x (# assets): the honest multiple-comparisons count for this
# independent-data confirmation family.
K: int = len(lead_specs()) * len(ASSETS)

__all__ = ["ASSETS", "K", "lead_specs"]
