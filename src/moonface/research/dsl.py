# src/moonface/research/dsl.py
"""Feature-expression DSL: the only channel by which LLM-proposed signals
enter the run. Whitelisted causal primitives only."""
from __future__ import annotations

import math
from statistics import fmean

from moonface.core.bundle import DataBundle

MAX_DEPTH = 8
MAX_WINDOW = 500
_SOURCES = ("close", "high", "low", "volume", "funding", "basis")
_WINDOW_OPS = ("sma", "zscore", "pct_rank", "lag")
_BINARY = ("gt", "lt")
_LOGIC = ("and", "or")

Series = list  # list[float | None]


def validate_expr(expr, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("expression too deep")
    if not isinstance(expr, dict) or "op" not in expr:
        raise ValueError("every node must be a dict with an 'op' key")
    op = expr["op"]
    if op == "src":
        if expr.get("name") not in _SOURCES:
            raise ValueError(f"unknown source {expr.get('name')!r}")
    elif op == "const":
        float(expr["v"])
    elif op == "const_bool":
        bool(expr["v"])
    elif op in _WINDOW_OPS:
        n = expr.get("n")
        if not isinstance(n, int) or not 2 <= n <= MAX_WINDOW:
            raise ValueError(f"{op}: n must be an int in [2, {MAX_WINDOW}]")
        validate_expr(expr["x"], depth + 1)
    elif op in _BINARY:
        validate_expr(expr["x"], depth + 1)
        validate_expr(expr["y"], depth + 1)
    elif op in _LOGIC:
        validate_expr(expr["x"], depth + 1)
        validate_expr(expr["y"], depth + 1)
    elif op == "not":
        validate_expr(expr["x"], depth + 1)
    elif op == "signal":
        validate_expr(expr["long"], depth + 1)
        validate_expr(expr["short"], depth + 1)
    else:
        raise ValueError(f"op {op!r} is not in the whitelist")


def _source(name: str, bundle: DataBundle) -> Series:
    if name in ("close", "high", "low", "volume"):
        return [getattr(c, name) for c in bundle.candles]
    series = getattr(bundle, name)  # funding | basis
    if series is None:
        raise ValueError(f"expression needs {name!r} but the bundle has none")
    return list(series)


def _window(values: Series, n: int, fn) -> Series:
    out: Series = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1:i + 1]
        if any(v is None for v in window):
            continue
        out[i] = fn(window)
    return out


def _series(expr: dict, bundle: DataBundle) -> Series:
    op = expr["op"]
    if op == "src":
        return _source(expr["name"], bundle)
    if op == "const":
        return [float(expr["v"])] * len(bundle.candles)
    if op == "lag":
        x = _series(expr["x"], bundle)
        n = expr["n"]
        return [None] * n + x[:-n] if n < len(x) else [None] * len(x)
    if op == "sma":
        return _window(_series(expr["x"], bundle), expr["n"], fmean)
    if op == "zscore":
        def z(w):
            mean = fmean(w)
            var = sum((v - mean) ** 2 for v in w) / (len(w) - 1)
            return 0.0 if var <= 0 else (w[-1] - mean) / math.sqrt(var)
        return _window(_series(expr["x"], bundle), expr["n"], z)
    if op == "pct_rank":
        def rank(w):
            return sum(1 for v in w if v <= w[-1]) / len(w)
        return _window(_series(expr["x"], bundle), expr["n"], rank)
    raise ValueError(f"not a series op: {op!r}")


def _bools(expr: dict, bundle: DataBundle) -> list[bool]:
    op = expr["op"]
    n = len(bundle.candles)
    if op == "const_bool":
        return [bool(expr["v"])] * n
    if op in _BINARY:
        xs, ys = _series(expr["x"], bundle), _series(expr["y"], bundle)
        if op == "gt":
            return [x is not None and y is not None and x > y
                    for x, y in zip(xs, ys)]
        return [x is not None and y is not None and x < y
                for x, y in zip(xs, ys)]
    if op == "and":
        xs, ys = _bools(expr["x"], bundle), _bools(expr["y"], bundle)
        return [x and y for x, y in zip(xs, ys)]
    if op == "or":
        xs, ys = _bools(expr["x"], bundle), _bools(expr["y"], bundle)
        return [x or y for x, y in zip(xs, ys)]
    if op == "not":
        return [not x for x in _bools(expr["x"], bundle)]
    raise ValueError(f"not a boolean op: {op!r}")


def evaluate_expr(expr: dict, bundle: DataBundle) -> list[tuple[int, str]]:
    validate_expr(expr)
    if expr["op"] != "signal":
        raise ValueError("top-level op must be 'signal'")
    longs = _bools(expr["long"], bundle)
    shorts = _bools(expr["short"], bundle)
    out: list[tuple[int, str]] = []
    for i in range(len(bundle.candles)):
        if longs[i] and not shorts[i]:
            out.append((i, "LONG"))
        elif shorts[i] and not longs[i]:
            out.append((i, "SHORT"))
    return out
