from __future__ import annotations

from moonface.feed.card import render_card
from moonface.feed.levels import Levels
from moonface.feed.setups import Setup


def _long():
    return Setup("sweep_choch", "LONG", 70, 100000.0, 90000.0, 95000.0, 1000.0)


def _levels():
    return Levels(entry=100000.0, entry_low=99750.0, entry_high=100250.0,
                  stop=89900.0, tp1=104000.0, tp2=108000.0, tp3=112000.0,
                  confidence=0.80)


def test_long_card_exact_text():
    card = render_card("BTC/USDT:USDT", _long(), _levels())
    assert card == (
        "🟢 BTCUSDT • LONG — Sell-side sweep + bullish CHoCH\n"
        "Entry: 99,750.00 – 100,250.00\n"
        "TP1: 104,000.00  TP2: 108,000.00  TP3: 112,000.00\n"
        "SL: 89,900.00\n"
        "Confidence: 0.80 (setup quality, NOT P(profit))\n"
        "Risk: ~1% — reference only, not execution sizing\n"
        "[SMC SETUP — heuristic; no validated out-of-sample edge]"
    )


def test_short_card_uses_red_arrow_and_bearish_name():
    s = Setup("bos_continuation", "SHORT", 70, 100000.0, None, 105000.0, 1000.0)
    card = render_card("ETH/USDT:USDT", s, _levels())
    assert card.startswith("🔴 ETHUSDT • SHORT — Bearish BOS continuation")
    assert "[SMC SETUP — heuristic; no validated out-of-sample edge]" in card
