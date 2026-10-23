# tests/test_research_dsl.py
import pytest

from moonface.research import dsl
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.kernel.synth import make_candles

# long when close > sma(20), short when close < sma(50)
EXPR = {"op": "signal",
        "long": {"op": "gt", "x": {"op": "src", "name": "close"},
                 "y": {"op": "sma", "n": 20, "x": {"op": "src", "name": "close"}}},
        "short": {"op": "lt", "x": {"op": "src", "name": "close"},
                  "y": {"op": "sma", "n": 50, "x": {"op": "src", "name": "close"}}}}


def test_validate_rejects_unknown_ops_and_depth():
    with pytest.raises(ValueError):
        dsl.validate_expr({"op": "exec", "cmd": "rm -rf /"})
    deep = {"op": "src", "name": "close"}
    for _ in range(dsl.MAX_DEPTH + 1):
        deep = {"op": "sma", "n": 5, "x": deep}
    with pytest.raises(ValueError):
        dsl.validate_expr(deep)
    with pytest.raises(ValueError):
        dsl.validate_expr({"op": "sma", "n": dsl.MAX_WINDOW + 1,
                           "x": {"op": "src", "name": "close"}})


def test_evaluate_emits_entries_with_sides():
    bundle = DataBundle(candles=make_candles(300))
    entries = dsl.evaluate_expr(EXPR, bundle)
    assert entries, "drifting synth data must trigger the long leg"
    assert all(side in ("LONG", "SHORT") for _i, side in entries)
    assert entries == sorted(entries)  # ordered by index


def test_no_lookahead_prefix_stability():
    """Truncating the future must not change past signals (causality)."""
    full = DataBundle(candles=make_candles(300))
    cut = 200
    trunc = DataBundle(candles=full.candles[:cut])
    full_entries = [(i, s) for i, s in dsl.evaluate_expr(EXPR, full) if i < cut]
    assert dsl.evaluate_expr(EXPR, trunc) == full_entries


def test_funding_source_requires_funding_data():
    expr = {"op": "signal",
            "long": {"op": "gt",
                     "x": {"op": "zscore", "n": 30,
                           "x": {"op": "src", "name": "funding"}},
                     "y": {"op": "const", "v": 2.0}},
            "short": {"op": "const_bool", "v": False}}
    bundle = DataBundle(candles=make_candles(100))
    with pytest.raises(ValueError):
        dsl.evaluate_expr(expr, bundle)


def test_generate_entries_routes_dsl_family():
    bundle = DataBundle(candles=make_candles(300))
    direct = dsl.evaluate_expr(EXPR, bundle)
    routed = generate_entries("dsl_expr", {"expr": EXPR}, bundle)
    assert routed == direct
