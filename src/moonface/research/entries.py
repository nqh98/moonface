from __future__ import annotations

from moonface.research.edge.basis_signals import make_basis_discount_reversion
from moonface.research.edge.divergence_signals import (
    make_price_oi_divergence, price_extension_short)
from moonface.research.edge.leadlag_signals import make_eth_lead_momentum
from moonface.research.edge.forced_error_signals import (
    failed_breakout_naive, make_failed_breakout_harvest,
    make_failed_fade_squeeze, make_funding_fade_long)
from moonface.research.edge.funding_signals import (make_funding_confirm,
                                                    make_funding_fade,
                                                    make_funding_flip)
from moonface.research.edge.ob_imbalance_signals import make_ob_imbalance_follow
from moonface.research.edge.positioning_signals import (
    make_oi_build_momentum, make_oi_flush_reversal, make_taker_flow_momentum,
    make_toptrader_follow)
from moonface.research.edge.regime_signals import seasonality, vol_regime
from moonface.research.edge.signals import (atr_channel_break, bb_breakout,
                                            bb_revert, donchian_break,
                                            ma_cross, price_vs_ma,
                                            reversion_in_range, roc_sign,
                                            smc_continuation)
from moonface.research.edge.system_signals import (liquidity_sweep_reclaim,
                                                    trend_pullback,
                                                    vol_compression_breakout,
                                                    vol_expansion)
from moonface.core.bundle import DataBundle

Entry = tuple[int, str]

PRICE_FAMILIES = {
    "ma_cross": ma_cross,
    "price_vs_ma": price_vs_ma,
    "roc_sign": roc_sign,
    "donchian_break": donchian_break,
    "atr_channel_break": atr_channel_break,
    "bb_breakout": bb_breakout,
    "bb_revert": bb_revert,
    "smc_continuation": smc_continuation,
    "reversion_in_range": reversion_in_range,
    "vol_regime": vol_regime,
    "seasonality": seasonality,
    "vol_compression_breakout": vol_compression_breakout,
    "vol_expansion": vol_expansion,
    "trend_pullback": trend_pullback,
    "liquidity_sweep_reclaim": liquidity_sweep_reclaim,
    "price_extension_short": price_extension_short,
    "failed_breakout_naive": failed_breakout_naive,
}

_FUNDING_FAMILIES = {
    "funding_fade": make_funding_fade,
    "funding_confirm": make_funding_confirm,
    "funding_flip": make_funding_flip,
    "funding_fade_long": make_funding_fade_long,
}

_POSITIONING_FAMILIES = {
    "oi_flush_reversal": make_oi_flush_reversal,
    "oi_build_momentum": make_oi_build_momentum,
    "toptrader_follow": make_toptrader_follow,
    "taker_flow_momentum": make_taker_flow_momentum,
    "price_oi_divergence": make_price_oi_divergence,
    "failed_breakout_harvest": make_failed_breakout_harvest,
}

_OI_FUNDING_FAMILIES = {
    "failed_fade_squeeze": make_failed_fade_squeeze,
}


class UnknownEntryFamily(KeyError):
    """The family has no generator yet (blocked domains land here)."""


def generate_entries(family: str, params: dict, bundle: DataBundle) -> list[Entry]:
    if family in PRICE_FAMILIES:
        return PRICE_FAMILIES[family](bundle.candles, params)
    if family in _FUNDING_FAMILIES:
        if bundle.funding is None:
            raise ValueError(f"{family} requires funding data in the bundle")
        return _FUNDING_FAMILIES[family](bundle.funding)(bundle.candles, params)
    if family == "basis_discount_reversion":
        if bundle.basis is None:
            raise ValueError("basis_discount_reversion requires basis data in the bundle")
        return make_basis_discount_reversion(bundle.basis)(bundle.candles, params)
    if family == "eth_lead_momentum":
        if bundle.feature is None:
            raise ValueError("eth_lead_momentum requires feature data in the bundle")
        return make_eth_lead_momentum(bundle.feature)(bundle.candles, params)
    if family in _POSITIONING_FAMILIES:
        if bundle.feature is None:
            raise ValueError(f"{family} requires feature data in the bundle")
        return _POSITIONING_FAMILIES[family](bundle.feature)(bundle.candles, params)
    if family == "ob_imbalance_follow":
        if bundle.bookdepth is None:
            raise ValueError(
                "ob_imbalance_follow requires bookdepth data in the bundle")
        return make_ob_imbalance_follow(bundle.bookdepth)(bundle.candles, params)
    if family == "dsl_expr":
        from moonface.research.dsl import evaluate_expr
        return evaluate_expr(params["expr"], bundle)
    if family in _OI_FUNDING_FAMILIES:
        if bundle.feature is None or bundle.funding is None:
            raise ValueError(
                f"{family} requires both OI feature and funding in the bundle")
        return _OI_FUNDING_FAMILIES[family](
            bundle.feature, bundle.funding)(bundle.candles, params)
    raise UnknownEntryFamily(family)


def known_families() -> set[str]:
    """Every family generate_entries can evaluate."""
    return (set(PRICE_FAMILIES) | set(_FUNDING_FAMILIES)
            | set(_POSITIONING_FAMILIES) | set(_OI_FUNDING_FAMILIES)
            | {"basis_discount_reversion", "eth_lead_momentum",
               "ob_imbalance_follow", "dsl_expr"})
