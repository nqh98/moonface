from __future__ import annotations

from moonface.core.indicators import donchian_channel, roc, sma
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.models.engine.deriv import funding_points_trend
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import DerivSnapshot, ModuleScore, TfViews
from moonface.models.engine.resample import resample

W_MACRO = 20
W_BREAKOUT = 20
W_MA_ALIGN = 10
W_ROC_STRONG = 20
W_ROC_WEAK = 10
W_PULLBACK = 15

# Frozen v2 panel params — module constants, deliberately NOT in EngineConfig
# (anti-overfitting: these lengths are not tunable). Values match the former
# EngineConfig defaults, so scorer behaviour is unchanged.
TREND_MA = 50
DONCHIAN_N = 40
PULLBACK_MA = 20
MOMENTUM_N = 12


def _has_funding_data(deriv: DerivSnapshot | None) -> bool:
    if deriv is None:
        return False
    return any(getattr(deriv, name, None) is not None
               for name in ("funding_pct", "funding_rate"))


def _score(module: str, direction: int, points: int, archetype: str,
           data_ok: bool, *evidence: str) -> ModuleScore:
    return ModuleScore(module=module, direction=direction, points=points,
                       archetype=archetype, data_ok=data_ok, evidence=evidence)


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def _ma_align_side(candles: list[Candle], fast: int, slow: int) -> int | None:
    if len(candles) < slow:
        return None
    closes = _closes(candles)
    close = closes[-1]
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    if close > slow_ma and fast_ma > slow_ma:
        return 1
    if close < slow_ma and fast_ma < slow_ma:
        return -1
    return 0


def _macro_score(views: TfViews, macro: MacroState, cfg) -> ModuleScore:
    # M1 is pure 1W macro bias (spec §2): a confirmed weekly bias scores +20 in
    # its direction, else 0. It takes NO 4h/panel inputs — the 4h SMA alignment
    # is M2's job (_ma_align_score), and opposition is handled by the gate, not
    # by damping M1 here (that double-counts 4h structure against breadth).
    del views, cfg
    effective = macro.effective()
    if effective == "BULL":
        return _score("m1_macro", 1, W_MACRO, "context", True,
                      "1w macro confirmed bull")
    if effective == "BEAR":
        return _score("m1_macro", -1, W_MACRO, "context", True,
                      "1w macro confirmed bear")
    return _score("m1_macro", 0, 0, "context", True,
                  f"1w macro {effective.lower()}")


def _breakout_score(views: TfViews, cfg) -> ModuleScore:
    del cfg  # panel lengths are frozen module constants
    candles = views.h4
    if len(candles) < DONCHIAN_N + 1:
        return _score("m2_breakout", 0, 0, "trend", False,
                      "need 4h breakout history")
    i = len(candles) - 1
    prior_high, prior_low = donchian_channel(candles, i, DONCHIAN_N)
    close = candles[i].close
    if close > prior_high:
        return _score("m2_breakout", 1, W_BREAKOUT, "trend", True,
                      "4h close above prior donchian high")
    if close < prior_low:
        return _score("m2_breakout", -1, W_BREAKOUT, "trend", True,
                      "4h close below prior donchian low")
    return _score("m2_breakout", 0, 0, "trend", True,
                  "4h close inside prior donchian channel")


def _ma_align_score(views: TfViews, cfg) -> ModuleScore:
    del cfg  # panel lengths are frozen module constants
    side = _ma_align_side(views.h4, PULLBACK_MA, TREND_MA)
    if side is None:
        return _score("m2_ma_align", 0, 0, "trend", False,
                      "need daily MA history")
    if side > 0:
        return _score("m2_ma_align", 1, W_MA_ALIGN, "trend", True,
                      "daily close and sma20 above sma50")
    if side < 0:
        return _score("m2_ma_align", -1, W_MA_ALIGN, "trend", True,
                      "daily close and sma20 below sma50")
    return _score("m2_ma_align", 0, 0, "trend", True,
                  "daily MA alignment absent")


def _roc_score(views: TfViews, cfg) -> ModuleScore:
    del cfg  # panel lengths are frozen module constants
    closes = _closes(views.h4)
    if len(closes) <= MOMENTUM_N:
        return _score("m3_roc", 0, 0, "trend", False,
                      "need daily ROC history")
    value = roc(closes, MOMENTUM_N)
    mag = abs(value)
    if mag >= 0.05:
        return _score("m3_roc", 1 if value > 0 else -1, W_ROC_STRONG, "trend", True,
                      f"daily roc={value:.4f}", "strong momentum")
    if mag >= 0.02:
        return _score("m3_roc", 1 if value > 0 else -1, W_ROC_WEAK, "trend", True,
                      f"daily roc={value:.4f}", "weak momentum")
    return _score("m3_roc", 0, 0, "trend", True,
                  f"daily roc={value:.4f}", "below momentum floor")


def _pullback_score(views: TfViews, cfg) -> ModuleScore:
    candles = views.h1
    need = max(TREND_MA, PULLBACK_MA, cfg.atr_period)
    if len(candles) < need:
        return _score("m4_pullback", 0, 0, "mean_revert", False,
                      "need 1h pullback history")
    side = _ma_align_side(candles, PULLBACK_MA, TREND_MA)
    if side == 0:
        return _score("m4_pullback", 0, 0, "mean_revert", True,
                      "trend not intact on 1h")
    closes = _closes(candles)
    fast_ma = sma(closes, PULLBACK_MA)
    band = 0.5 * atr(candles, cfg.atr_period)
    if band <= 0:
        return _score("m4_pullback", 0, 0, "mean_revert", False,
                      "atr unavailable for pullback band")
    distance = abs(closes[-1] - fast_ma)
    if distance <= band:
        return _score("m4_pullback", side, W_PULLBACK, "mean_revert", True,
                      f"distance_to_sma20={distance:.4f}", f"band={band:.4f}")
    return _score("m4_pullback", 0, 0, "mean_revert", True,
                  f"distance_to_sma20={distance:.4f}", f"band={band:.4f}")


def _funding_score(deriv: DerivSnapshot | None) -> ModuleScore:
    if not _has_funding_data(deriv):
        return _score("m5_funding", 0, 0, "context", False,
                      "funding unavailable")
    long_points, long_evidence = funding_points_trend(deriv, 1)
    short_points, short_evidence = funding_points_trend(deriv, -1)
    if long_points > short_points:
        return _score("m5_funding", 1, long_points, "context", True, long_evidence)
    if short_points > long_points:
        return _score("m5_funding", -1, short_points, "context", True, short_evidence)
    return _score("m5_funding", 0, long_points, "context", True, long_evidence)


def score(views: TfViews, macro: MacroState, deriv: DerivSnapshot | None,
          cfg) -> list[ModuleScore]:
    return [
        _macro_score(views, macro, cfg),
        _breakout_score(views, cfg),
        _ma_align_score(views, cfg),
        _roc_score(views, cfg),
        _pullback_score(views, cfg),
        _funding_score(deriv),
    ]


def build_views(candles_1h: list[Candle]) -> TfViews:
    return TfViews(
        h1=candles_1h,
        h4=resample(candles_1h, "4h"),
        d1=resample(candles_1h, "1d"),
        w1=resample(candles_1h, "1w"),
    )
