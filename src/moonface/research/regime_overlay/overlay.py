from __future__ import annotations

from moonface.research.regime_overlay.regime import regime_at

SIZE_RISKOFF_FACTOR = 0.5
MODES = ("directional", "derisk", "size")


def apply_overlay(trades, candles, regime_def, macro, mode) -> list[tuple[int, float]]:
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    out: list[tuple[int, float]] = []
    for t in trades:
        entry_ts = candles[t.entry_index].timestamp_ms
        exit_ts = candles[t.exit_index].timestamp_ms
        reg = regime_at(entry_ts, regime_def, macro)
        if mode == "directional":
            keep = (reg == "risk_on" and t.side == "BUY") or (
                reg == "risk_off" and t.side == "SELL")
            if keep:
                out.append((exit_ts, t.r_multiple))
        elif mode == "derisk":
            if reg == "risk_on":
                out.append((exit_ts, t.r_multiple))
        else:  # size
            f = 1.0 if reg == "risk_on" else SIZE_RISKOFF_FACTOR
            out.append((exit_ts, round(t.r_multiple * f, 6)))
    return out
