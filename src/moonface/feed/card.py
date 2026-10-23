"""Render a Setup + Levels as a single Telegram message string. Pure function."""
from __future__ import annotations

from moonface.feed.levels import Levels
from moonface.feed.setups import Setup

_NAMES = {
    ("sweep_choch", "LONG"): "Sell-side sweep + bullish CHoCH",
    ("sweep_choch", "SHORT"): "Buy-side sweep + bearish CHoCH",
    ("bos_continuation", "LONG"): "Bullish BOS continuation",
    ("bos_continuation", "SHORT"): "Bearish BOS continuation",
}

_CAVEAT = "[SMC SETUP — heuristic; no validated out-of-sample edge]"


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def render_card(symbol: str, setup: Setup, levels: Levels) -> str:
    arrow = "🟢" if setup.side == "LONG" else "🔴"
    clean = symbol.split(":")[0].replace("/", "")
    name = _NAMES[(setup.setup_type, setup.side)]
    return (
        f"{arrow} {clean} • {setup.side} — {name}\n"
        f"Entry: {_fmt(levels.entry_low)} – {_fmt(levels.entry_high)}\n"
        f"TP1: {_fmt(levels.tp1)}  TP2: {_fmt(levels.tp2)}  TP3: {_fmt(levels.tp3)}\n"
        f"SL: {_fmt(levels.stop)}\n"
        f"Confidence: {levels.confidence:.2f} (setup quality, NOT P(profit))\n"
        f"Risk: ~1% — reference only, not execution sizing\n"
        f"{_CAVEAT}"
    )
