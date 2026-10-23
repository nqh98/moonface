"""BTC distributional path signal — model-agnostic foundation.

Pipeline: features (point-in-time) + labels (forward path) -> dataset ->
purged walk-forward folds -> predictor -> policy (LONG/SHORT/WAIT + size) ->
dual-frame evaluation gate. Design frozen in
experiments/path_signal/PREREGISTRATION.md."""

from moonface.research.pathsig.dataset import Sample, build_dataset
from moonface.research.pathsig.evaluate import evaluate_strategy, realized_r
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel, build_labels
from moonface.research.pathsig.policy import Decision, Distribution, decide
from moonface.research.pathsig.walkforward import Fold, walk_forward_folds

__all__ = [
    "Sample", "build_dataset", "evaluate_strategy", "realized_r",
    "FEATURE_NAMES", "PathLabel", "build_labels", "Decision", "Distribution",
    "decide", "Fold", "walk_forward_folds",
]
