"""Paper-emission adapter for the frozen BTC MTF regime-quality LONG-only cell.

This is the one signal that survived the market-neutral (BTC-beta) hedge —
BTC's own counter-trend dip-buy inside a 4h up-regime — decomposed to its
edge-carrying long side (`experiments/mtf/LONG_ONLY.md`,
`LONG_ONLY_FORWARD_REGISTRATION.md`). It is a PAPER-ONLY adapter (Signal tier
"paper"; never the live execution path, never places orders): it bridges to the
frozen `research.mtf` entry so the live decision is byte-identical to the
registered backtest — no reimplementation, no drift, no strategy change.

Contract projection: a LONG entry on the last closed 15m bar -> LONG/paper; the
SHORT side of the same cell is DISCARDED (long-only registration); anything else
-> WAIT. The cell is no-stop (2-day time hold), so no price invalidation is
emitted; the hold/exit is documented in risk_notes and realized by the forward
report. The registered trade set applies non-overlap spacing, which a stateless
per-candle watch cannot; the authoritative REAFFIRM/DOWNGRADE resolution re-runs
`tools/mtf_long_only.py` over the accumulated forward window (which applies the
frozen non-overlap + exit + cost). This adapter emits + journals every qualifying
bar so the live tape is visible.
"""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.research.mtf.evaluate import cell_gen
from moonface.research.mtf.grid import broaden_best_cell
from moonface.models.evaluate import Signal, sentinel_extended, wait
from moonface.strategies.registry import register

# 4h SMA50 + rolling_std(50) gate needs >=50 closed 4h bars = 800 15m bars;
# 1200 gives ~75 4h bars of warmed-up bias plus RSI/ATR margin.
_LOOKBACK_BARS = 1200
_HOLD_DAYS = 2


@register
class MtfLongStrategy:
    family = "mtf_long"
    # Honored by the watch loop's strategy tier so the 15m base gets enough
    # history to warm the 4h regime gate (default LOOKBACK_BARS=600 is too short).
    lookback_bars = _LOOKBACK_BARS

    def validate(self, strategy) -> bool:
        params = strategy.params or {}
        exit_ = strategy.exit or {}
        # params document the frozen identity; the entry logic is hardcoded to
        # broaden_best_cell() below, so it cannot silently drift from the spec.
        return (params.get("cell") == "broaden_best"
                and params.get("long_only") is True
                and exit_.get("name") == "horizon_hold"
                and isinstance(exit_.get("params"), dict)
                and exit_["params"].get("n_bars") == _HOLD_DAYS * 96)

    def evaluate(self, strategy, bundle: DataBundle) -> Signal:
        cell = broaden_best_cell()
        candles = bundle.candles
        # need enough base bars to close 50 4h bars for the trend-strength gate
        if len(candles) < 50 * 16 + 2:
            return wait("insufficient history for the 4h regime-quality gate")
        last_index = len(candles) - 1
        # rsi_reversion stops one bar early; the sentinel lets the real last
        # closed bar be evaluated (entries at the sentinel index are ignored).
        extended = sentinel_extended(bundle)
        sides = {i: side for i, side in cell_gen(cell)(extended.candles)}
        side = sides.get(last_index)
        price = candles[last_index].close
        notes = ("4h trend-quality up-regime (|close-SMA50|>=1σ) + 15m RSI<=30 "
                 f"dip; {_HOLD_DAYS}-day time hold, NO stop; paper signal only, "
                 "no order is placed")
        if side == "LONG":
            return Signal(decision="LONG", price=price, invalidation=None,
                          fraction=strategy.fraction,
                          reason="mtf_long broaden_best fired LONG (paper)",
                          timeframe="15m", risk_notes=notes, tier="paper")
        # SHORT side of the cell is intentionally discarded (long-only), and a
        # no-entry bar is a WAIT. This adapter never emits SHORT.
        return Signal(decision="WAIT", price=None, invalidation=None,
                      fraction=None, reason="no mtf_long entry on the last "
                      "closed candle", timeframe="15m", risk_notes=notes,
                      tier="paper")


MTF_LONG = MtfLongStrategy()
