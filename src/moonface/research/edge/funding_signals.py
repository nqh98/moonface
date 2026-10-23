from __future__ import annotations

from collections.abc import Callable
from statistics import fmean, pstdev

from moonface.core.models import Candle

Generator = Callable[[list[Candle], dict], list[tuple[int, str]]]


def make_funding_fade(funding: list[float | None]) -> Generator:
    """Fade extreme funding (crowding -> mean revert). Rolling z-score over `window`
    bars; z >= +z_thr (crowded long) -> SHORT, z <= -z_thr -> LONG. Edge-triggered:
    emits only when the chosen side becomes newly true."""

    def gen(h1: list[Candle], params: dict) -> list[tuple[int, str]]:
        window, z_thr = params["window"], params["z_thr"]
        out: list[tuple[int, str]] = []
        prev_side: str | None = None
        for i in range(min(len(h1), len(funding))):
            if i + 1 < window:
                prev_side = None
                continue
            recent = funding[i + 1 - window : i + 1]
            if any(v is None for v in recent):
                prev_side = None
                continue
            mean = fmean(recent)
            sd = pstdev(recent)
            side: str | None = None
            if sd > 0:
                z = (recent[-1] - mean) / sd
                if z >= z_thr:
                    side = "SHORT"
                elif z <= -z_thr:
                    side = "LONG"
            if side is not None and side != prev_side:
                out.append((i, side))
            prev_side = side
        return out

    return gen


def make_funding_confirm(funding: list[float | None]) -> Generator:
    """Trend-follow persistent funding. Same sign for `persist` consecutive bars AND
    current |rate| >= `lvl` -> trade WITH the sign (positive funding = longs paying =
    bullish -> LONG). Edge-triggered."""

    def gen(h1: list[Candle], params: dict) -> list[tuple[int, str]]:
        persist, lvl = params["persist"], params["lvl"]
        out: list[tuple[int, str]] = []
        prev_side: str | None = None
        for i in range(min(len(h1), len(funding))):
            if i + 1 < persist:
                prev_side = None
                continue
            recent = funding[i + 1 - persist : i + 1]
            if any(v is None for v in recent):
                prev_side = None
                continue
            side: str | None = None
            if all(v > 0 for v in recent) and recent[-1] >= lvl:
                side = "LONG"
            elif all(v < 0 for v in recent) and -recent[-1] >= lvl:
                side = "SHORT"
            if side is not None and side != prev_side:
                out.append((i, side))
            prev_side = side
        return out

    return gen


def make_funding_flip(funding: list[float | None]) -> Generator:
    """Trade funding sign changes. prev <= 0 < cur -> LONG; prev > 0 >= cur -> SHORT.
    `debounce` suppresses any re-fire within that many bars of the last one."""

    def gen(h1: list[Candle], params: dict) -> list[tuple[int, str]]:
        debounce = params["debounce"]
        out: list[tuple[int, str]] = []
        last_fire = -(10**9)
        for i in range(1, min(len(h1), len(funding))):
            prev, cur = funding[i - 1], funding[i]
            if prev is None or cur is None:
                continue
            side: str | None = None
            if prev <= 0 < cur:
                side = "LONG"
            elif prev > 0 >= cur:
                side = "SHORT"
            if side is not None and i - last_fire >= debounce:
                out.append((i, side))
                last_fire = i
        return out

    return gen