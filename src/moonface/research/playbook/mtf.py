from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle


def align_higher(h1: list[Candle], higher: list[Candle], higher_tf_ms: int,
                 tf1_ms: int) -> list[int]:
    """k[i] = count of `higher` bars whose close (open+higher_tf_ms) is <= the
    close of h1[i] (open+tf1_ms). Two-pointer; both inputs timestamp-sorted."""
    k: list[int] = []
    j = 0
    n = len(higher)
    for c in h1:
        h1_close = c.timestamp_ms + tf1_ms
        while j < n and higher[j].timestamp_ms + higher_tf_ms <= h1_close:
            j += 1
        k.append(j)
    return k


def _infer_tf_ms(candles: list[Candle], default: int) -> int:
    if len(candles) >= 2:
        return candles[1].timestamp_ms - candles[0].timestamp_ms
    return default


@dataclass
class MTFView:
    h1: list[Candle]
    h2: list[Candle]
    h4: list[Candle]
    tf1_ms: int
    tf2_ms: int
    tf4_ms: int

    @classmethod
    def build(cls, h1: list[Candle], h2: list[Candle], h4: list[Candle]) -> "MTFView":
        tf1 = _infer_tf_ms(h1, 3_600_000)
        tf2 = _infer_tf_ms(h2, 2 * 3_600_000)
        tf4 = _infer_tf_ms(h4, 4 * 3_600_000)
        v = cls(h1, h2, h4, tf1, tf2, tf4)
        v._k2 = align_higher(h1, h2, tf2, tf1)
        v._k4 = align_higher(h1, h4, tf4, tf1)
        return v

    def h2_prefix(self, i: int) -> list[Candle]:
        return self.h2[: self._k2[i]]

    def h4_prefix(self, i: int) -> list[Candle]:
        return self.h4[: self._k4[i]]
