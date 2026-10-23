"""Compatibility wrapper for the tournament evaluator.

The live implementation lives in `explore.py`; this module re-exports the same
API so the CLI and older imports keep working.
"""
from __future__ import annotations

from moonface.research.ls_tournament.explore import (  # noqa: F401
    _evaluate_records,
    _slice_context,
    evaluate_config,
    run_explore,
)

__all__ = [
    "_evaluate_records",
    "_slice_context",
    "evaluate_config",
    "run_explore",
]

