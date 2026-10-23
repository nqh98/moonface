"""Train-only selection + stricter economic sealed-holdout verdict (spec §6-§7)."""
from __future__ import annotations

# Reuse the byte-identical train qualifier from the ADX-gate control.
from moonface.research.donchian_filter.select import qualifies  # noqa: F401
from moonface.research.donchian_filter.grid import HOLDOUT_MIN_TRADES

PAPER_CANDIDATE = "PAPER_CANDIDATE"
NEGATIVE = "NEGATIVE"
INACTIVE = "INACTIVE"


def select_cell(rows) -> str | None:
    """Among train qualifiers, pick least-negative train max_dd_r; tie-break
    robust_frac then net_r. Returns the cell id or None."""
    qs = [r for r in rows if r["qualifies"]]
    if not qs:
        return None
    qs.sort(
        key=lambda r: (r["gated"]["max_dd_r"], r["robust_frac"], r["gated"]["net_r"]),
        reverse=True,
    )
    return qs[0]["cell"]


def sealed_verdict(base_m, gated_m, min_trades: int = HOLDOUT_MIN_TRADES) -> str:
    """Economic bar (spec §7): PAPER_CANDIDATE only if the gated sealed slice is
    genuinely tradeable, not merely less-bad than the base."""
    if gated_m["n"] < min_trades:
        return INACTIVE
    if (
        gated_m["net_r"] > 0.0
        and gated_m["profit_factor"] >= 1.0
        and gated_m["max_dd_r"] > base_m["max_dd_r"]
        and gated_m["net_r"] > base_m["net_r"]
    ):
        return PAPER_CANDIDATE
    return NEGATIVE
