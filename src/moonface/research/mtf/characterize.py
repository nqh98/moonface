"""Descriptive characterization of one MTF cell's standalone edge on one asset.

NOT a selection, gate, or new cell -- it decomposes an already-frozen cell's
single faithful trade stream to show WHERE the edge lives:

  - side attribution  : the long book (counter-trend dip-buys inside an up-regime)
                        vs the short book (rip-sells inside a down-regime),
  - outlier dependence: expectancy with the top-K winners removed, and the share
                        of gross profit carried by the fattest trades -- the
                        program's recurring "edge is 3 trades" failure mode,
  - distribution      : win rate, payoff asymmetry, skew/kurtosis,
  - excursion path    : per-trade max adverse / favorable excursion (why the
                        counter-trend dip-buy needs room and a 2-day hold).

Every record is resolved through `resolve_trade_span`, whose net_r is identical
to the single-path stream, so this is the SAME trade set the basket trades. Pure
module; callers supply candles. Free OHLCV; paper research."""
from __future__ import annotations

from statistics import median

from moonface.core.metrics import (_kurtosis, _skew, resolve_trade_span,
                                          summarize_r)
from moonface.research.mtf.evaluate import cell_gen
from moonface.research.mtf.grid import MtfCell
from moonface.features.oi_features import nonoverlap

Record = dict  # {ts, side, net_r, mae_r, mfe_r}


def enriched_trades(candles, cell: MtfCell) -> list[Record]:
    """Per-trade records with the gross excursion path over the hold. atr_frac
    converts a price fraction into the same R units as net_r, so MAE/MFE are in
    R. MAE <= 0 <= MFE by construction (entry bar contributes both bounds)."""
    out: list[Record] = []
    for i, side in nonoverlap(cell_gen(cell)(candles), cell.h):
        span = resolve_trade_span(candles, i, side, cell.exit_name,
                                  cell.exit_params)
        if span is None:
            continue
        ei, xi, net_r, atr_frac = span
        if atr_frac <= 0:
            continue
        entry_px = candles[ei].close
        adverse = favorable = 0.0
        for c in candles[ei:xi + 1]:
            if side == "LONG":
                hi = (c.high / entry_px - 1.0) / atr_frac
                lo = (c.low / entry_px - 1.0) / atr_frac
            else:  # short: a rising price is adverse
                hi = -(c.low / entry_px - 1.0) / atr_frac
                lo = -(c.high / entry_px - 1.0) / atr_frac
            favorable = max(favorable, hi)
            adverse = min(adverse, lo)
        out.append({"ts": candles[ei].timestamp_ms, "side": side,
                    "net_r": net_r, "mae_r": adverse, "mfe_r": favorable})
    return out


def _path_dd(rs: list[float]) -> float:
    eq = peak = mdd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return round(mdd, 2)


def book_stats(records: list[Record], side: str | None = None) -> dict:
    """summarize_r on the (optionally side-filtered) net_r stream, plus the
    faithful single-path drawdown and MAR for that book."""
    sel = [r for r in records if side is None or r["side"] == side]
    rs = [r["net_r"] for r in sel]
    s = summarize_r(rs)
    dd = _path_dd(rs)
    return {"n": s.trade_count,
            "longs": sum(1 for r in sel if r["side"] == "LONG"),
            "shorts": sum(1 for r in sel if r["side"] == "SHORT"),
            "pf": s.profit_factor, "expectancy_r": s.expectancy_r,
            "win_rate": s.win_rate, "total_r": round(s.total_r, 2),
            "max_dd_r": dd, "mar": round(abs(s.total_r / dd), 4) if dd else 0.0,
            "positive": s.total_r > 0}


def distribution(records: list[Record]) -> dict:
    """Win rate, average win/loss, payoff ratio, skew, kurtosis over net_r."""
    rs = [r["net_r"] for r in records]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return {"n": len(rs),
            "win_rate": round(len(wins) / len(rs), 4) if rs else 0.0,
            "avg_win_r": round(avg_win, 4), "avg_loss_r": round(avg_loss, 4),
            "payoff": round(avg_win / abs(avg_loss), 4) if avg_loss else 0.0,
            "skew": round(_skew(rs), 4), "kurtosis": round(_kurtosis(rs), 4),
            "best_r": round(max(rs), 3) if rs else 0.0,
            "worst_r": round(min(rs), 3) if rs else 0.0}


def outlier_dependence(records: list[Record], ks=(1, 3, 5, 10)) -> dict:
    """Expectancy and total R with the top-K WINNERS removed, and the share of
    gross profit carried by the top 5% of trades. An edge whose expectancy goes
    non-positive after dropping a handful of winners is outlier-carried (the
    program's recurring kill), not a broad edge."""
    rs = sorted((r["net_r"] for r in records), reverse=True)
    n = len(rs)
    total = sum(rs)
    ex = {}
    for k in ks:
        if k < n:
            rem = rs[k:]
            ex[k] = {"expectancy_r": round(sum(rem) / len(rem), 4),
                     "total_r": round(sum(rem), 2), "positive": sum(rem) > 0}
    gross_win = sum(r for r in rs if r > 0)
    top5 = max(1, n // 20)
    top5_win = sum(r for r in rs[:top5] if r > 0)
    return {"n": n, "total_r": round(total, 2), "ex_top_k": ex,
            "top5pct_count": top5,
            "top5pct_profit_share": round(top5_win / gross_win, 4)
            if gross_win else 0.0}


def excursion_summary(records: list[Record]) -> dict:
    """Median MAE/MFE overall and split by outcome. Winners that ran deep
    underwater first (MAE << 0) before paying show the dip-buy needs room -- the
    mechanism reason a tight stop destroys the edge."""
    if not records:
        return {"n": 0}
    mae = [r["mae_r"] for r in records]
    mfe = [r["mfe_r"] for r in records]
    win_mae = [r["mae_r"] for r in records if r["net_r"] > 0]
    loss_mae = [r["mae_r"] for r in records if r["net_r"] <= 0]
    return {"n": len(records),
            "median_mae_r": round(median(mae), 3),
            "median_mfe_r": round(median(mfe), 3),
            "median_mae_winners_r": round(median(win_mae), 3) if win_mae else 0.0,
            "median_mae_losers_r": round(median(loss_mae), 3) if loss_mae else 0.0}
