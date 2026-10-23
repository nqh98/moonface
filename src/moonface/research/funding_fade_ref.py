# src/moonface/research/funding_fade_ref.py
"""BTC Q1 reference for the funding_fade transfer program (spec 2026-06-15).

Answers the literal "unpulled lever" question: does funding_fade's bounded-exit
edge, rejected on BTC only by the fixed -15R cap, show a positive MAR once the
absolute cap is swapped for the leverage-clamped sizing frame? This is an
IN-SAMPLE reference on the contaminated/selected asset: reported, never a
validation. It imports neither the store nor the lockbox, so it can never spend
a one-touch tail.
"""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.research.domains import (FUNDING_FADE_TRANSFER_ENTRY,
                                       FUNDING_FADE_TRANSFER_EXITS,
                                       TRANSFER_FRACTION)
from moonface.research.ladder import r_stream
from moonface.core.metrics import EquitySummary, equity_summary
from moonface.kernel.spec import HypothesisSpec

BTC_REF_ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
                 "timeframe": "4h", "funding_symbol": "BTC/USDT:USDT"}


def reference_rows() -> list[tuple[str, dict]]:
    """The two frozen bounded exits, in registered order."""
    return list(FUNDING_FADE_TRANSFER_EXITS)


def _spec(exit_name: str, exit_params: dict) -> HypothesisSpec:
    fam, ep = FUNDING_FADE_TRANSFER_ENTRY
    return HypothesisSpec(domain="funding_fade_ref", version=1,
                          asset=BTC_REF_ASSET,
                          entry={"family": fam, "params": ep},
                          exit={"name": exit_name, "params": exit_params},
                          fraction=TRANSFER_FRACTION)


def btc_reference(bundle: DataBundle) -> dict[str, EquitySummary]:
    """Full-window (no fence) sizing-frame metrics per exit. The whole BTC
    window is in-sample by design; there is no holdout split here."""
    out: dict[str, EquitySummary] = {}
    for name, params in reference_rows():
        spec = _spec(name, params)
        trades = [(r, af) for _, r, af in r_stream(spec, bundle)]
        out[name] = equity_summary(trades, TRANSFER_FRACTION)
    return out


def format_reference(summaries: dict[str, EquitySummary]) -> str:
    lines = [
        "funding_fade BTC reference (Q1) — IN-SAMPLE REFERENCE, NOT VALIDATION.",
        "The BTC tail is contaminated (selection was performed on it); these",
        "numbers re-express the discovery finding under the sizing frame only.",
        "",
        f"entry: funding_fade {FUNDING_FADE_TRANSFER_ENTRY[1]}  "
        f"fraction: {TRANSFER_FRACTION}",
        "",
        f"{'exit':<14} {'trades':>7} {'MAR':>10} {'Sharpe':>9} "
        f"{'netRet':>10} {'maxDD%':>9}",
    ]
    for name, s in summaries.items():
        dd_pct = s.max_drawdown * 100.0
        mar = "inf" if s.mar == float("inf") else f"{s.mar:.3f}"
        lines.append(f"{name:<14} {s.trade_count:>7} {mar:>10} "
                     f"{s.sharpe:>9.4f} {s.net_return:>10.4f} {dd_pct:>8.2f}%")
    return "\n".join(lines)
