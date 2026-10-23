from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from moonface.core.bundle import DataBundle


@dataclass(frozen=True)
class FencedBundle:
    """The only data path inside research/. Stages 1-3 receive research() and
    mechanically cannot see candles at/after fence_ts. The runner reads .full
    for the lockbox stage only after Store.touch_lockbox() succeeds (set-once)."""

    full: DataBundle
    fence_ts: int

    @property
    def fence_index(self) -> int:
        stamps = [c.timestamp_ms for c in self.full.candles]
        return bisect_left(stamps, self.fence_ts)

    def research(self) -> DataBundle:
        i = self.fence_index
        return DataBundle(
            candles=self.full.candles[:i],
            funding=self.full.funding[:i] if self.full.funding is not None else None,
            basis=self.full.basis[:i] if self.full.basis is not None else None,
            feature=self.full.feature[:i] if self.full.feature is not None else None,
        )
