"""Step C - ablation baselines (the benchmark floor). Infrastructure only."""

from moonface.research.matrix.baselines.costs import CostModel
from moonface.research.matrix.baselines.metrics import BaselineMetrics, baseline_metrics
from moonface.research.matrix.baselines.strategies import (
    BaselineTrade,
    donchian_reverse,
    donchian_reverse_frozen,
)

__all__ = [
    "CostModel",
    "BaselineMetrics",
    "baseline_metrics",
    "BaselineTrade",
    "donchian_reverse",
    "donchian_reverse_frozen",
]
