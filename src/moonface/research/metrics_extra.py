from __future__ import annotations

from moonface.core.metrics import Summary, summarize_r
from moonface.features.simulate import Trade


def summarize(trades: list[Trade]) -> Summary:
    # Only filled, resolved trades carry an R multiple; NO_FILL trades are ignored.
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    return summarize_r(rs)
