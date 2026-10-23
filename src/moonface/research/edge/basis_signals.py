from __future__ import annotations

from collections.abc import Callable

from moonface.core.models import Candle

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]


def _percentile_rank(values: list[float], x: float) -> float:
    """Percentile rank of *x* within *values*.

    ``count(values < x) / (n - 1) * 100`` where n = len(values).
    Returns 50.0 when all values are identical.
    """
    n = len(values)
    if n <= 1:
        return 50.0
    below = sum(1 for v in values if v < x)
    return below / (n - 1) * 100.0


def make_basis_discount_reversion(basis: list[float | None]) -> Generator:
    """Spot-perp basis deep-discount / rich-premium mean reversion.

    Rolling percentile rank over `window` bars:
      - rank crosses **below** `pct` (deep discount)  -> LONG
      - rank crosses **above** `100 - pct` (rich premium) -> SHORT
    Edge-triggered: emits only when the chosen side becomes newly true.
    Bars with ``None`` in the window are skipped and ``prev_side`` resets.
    """

    def gen(h1: list[Candle], params: dict) -> list[tuple[int, str]]:
        window, pct = params["window"], params["pct"]
        out: list[tuple[int, str]] = []
        prev_side: str | None = None
        for i in range(min(len(h1), len(basis))):
            if i + 1 < window:
                prev_side = None
                continue
            recent = basis[i + 1 - window : i + 1]
            if any(v is None for v in recent):
                prev_side = None
                continue
            rank = _percentile_rank(recent, recent[-1])
            side: str | None = None
            if rank < pct:
                side = "LONG"
            elif rank > 100 - pct:
                side = "SHORT"
            if side is not None and side != prev_side:
                out.append((i, side))
            prev_side = side
        return out

    return gen
