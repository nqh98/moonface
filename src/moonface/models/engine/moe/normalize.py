from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from statistics import median

from moonface.models.engine.moe.config_moe import MoeConfig


@dataclass(frozen=True)
class Normalizer:
    mode: str
    abs_sorted: dict[str, list[float]] = field(default_factory=dict)
    center: dict[str, float] = field(default_factory=dict)
    scale: dict[str, float] = field(default_factory=dict)

    @classmethod
    def fit(cls, raw_by_expert: dict[str, list[float]], cfg: MoeConfig) -> "Normalizer":
        abs_sorted: dict[str, list[float]] = {}
        center: dict[str, float] = {}
        scale: dict[str, float] = {}
        for name, raws in raw_by_expert.items():
            nonzero = [raw for raw in raws if raw != 0.0]
            abs_sorted[name] = sorted(abs(raw) for raw in nonzero)
            if nonzero:
                med = median(nonzero)
                mad = median([abs(raw - med) for raw in nonzero]) or 1e-9
                center[name] = med
                scale[name] = 1.4826 * mad
            else:
                center[name] = 0.0
                scale[name] = 1.0
        return cls(cfg.norm_mode, abs_sorted, center, scale)

    def transform(self, name: str, raw: float) -> float:
        if raw == 0.0 or name not in self.abs_sorted:
            return 0.0
        if self.mode == "tanh":
            z = (raw - self.center[name]) / self.scale[name]
            return math.tanh(z)
        arr = self.abs_sorted[name]
        if not arr:
            return 0.0
        rank = (bisect.bisect_right(arr, abs(raw)) + 1) / (len(arr) + 1)
        return (1.0 if raw > 0.0 else -1.0) * rank
