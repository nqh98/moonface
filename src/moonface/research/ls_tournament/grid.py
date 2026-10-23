"""Frozen long/short tournament grid for BTC practical research.

The grid is deliberately compact and fully enumerated: 20 group templates per
timeframe, each with 3 swept axis points, for 60 configs per timeframe and 120
total across 2h and 4h.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

TIMEFRAMES = ("2h", "4h")

_ATR_PERIOD = 14
_TREND_EXIT = {
    "2h": {"atr_trail": {"k_trail": 2.0, "max_bars": 120, "atr_period": _ATR_PERIOD},
           "donchian_trail": {"k_stop": 2.0, "trail_n": 20, "max_bars": 120,
                              "atr_period": _ATR_PERIOD},
           "chandelier": {"atr_mult": 4.0, "max_bars": 120, "atr_period": _ATR_PERIOD}},
    "4h": {"atr_trail": {"k_trail": 2.0, "max_bars": 120, "atr_period": _ATR_PERIOD},
           "donchian_trail": {"k_stop": 2.0, "trail_n": 20, "max_bars": 120,
                              "atr_period": _ATR_PERIOD},
           "chandelier": {"atr_mult": 4.0, "max_bars": 120, "atr_period": _ATR_PERIOD}},
}
_MR_EXIT = {
    "2h": {"fixed_bracket": {"k_stop": 2.0, "m_tp": 4.0, "atr_period": _ATR_PERIOD}},
    "4h": {"fixed_bracket": {"k_stop": 2.0, "m_tp": 4.0, "atr_period": _ATR_PERIOD}},
}


@dataclass(frozen=True, slots=True)
class ExploreConfig:
    label: str
    timeframe: str
    long_rule: dict
    short_rule: dict
    filters: tuple[dict, ...]
    exit_name: str
    exit_params: dict
    h: int
    group: str
    axis: float


@dataclass(frozen=True, slots=True)
class _TemplateSpec:
    name: str
    axis_name: str
    axis_values: tuple[float, float, float]
    exit_name: str
    h: int
    build: Callable[[float, str], tuple[dict, dict, tuple[dict, ...]]]


def _rule(family: str, params: dict) -> dict:
    return {"family": family, "params": dict(params)}


def _filter(name: str, params: dict) -> dict:
    return {"name": name, "params": dict(params)}


def _sig(mapping: dict) -> str:
    return ",".join(f"{k}={mapping[k]}" for k in sorted(mapping))


def _exit_sig(exit_name: str, exit_params: dict) -> str:
    return f"{exit_name}:{_sig(exit_params)}"


_INT_PARAM_KEYS = {"n", "slow", "period", "squeeze_n", "window", "lookback", "trail_n", "max_bars"}


def _coerce_param(name: str, value: float) -> int | float:
    if name in _INT_PARAM_KEYS:
        return int(round(value))
    return int(round(value)) if float(value).is_integer() else float(value)


def _label(tf: str, name: str, axis_name: str, axis: float,
           long_rule: dict, short_rule: dict, filters: tuple[dict, ...],
           exit_name: str, exit_params: dict) -> str:
    parts = [
        tf, name, f"{axis_name}={axis:g}",
        f"long={long_rule['family']}({_sig(long_rule['params'])})",
        f"short={short_rule['family']}({_sig(short_rule['params'])})",
    ]
    if filters:
        parts.append("filters=" + "|".join(
            f"{f['name']}({_sig(f['params'])})" for f in filters))
    parts.append(_exit_sig(exit_name, exit_params))
    return ":".join(parts)


def _group(tf: str, name: str, long_rule: dict, short_rule: dict,
           filters: tuple[dict, ...], exit_name: str, exit_params: dict,
           axis_name: str) -> str:
    parts = [
        tf,
        name,
        f"long={long_rule['family']}",
        f"short={short_rule['family']}",
    ]
    if filters:
        parts.append("filters=" + "|".join(f["name"] for f in filters))
    parts.append(exit_name)
    return ":".join(parts)


def _core_builder(family: str, axis_key: str, fixed: dict,
                  filters: tuple[dict, ...] = ()) -> Callable[[float, str], tuple[dict, dict, tuple[dict, ...]]]:
    def build(axis: float, tf: str) -> tuple[dict, dict, tuple[dict, ...]]:
        params = {**fixed, axis_key: _coerce_param(axis_key, axis)}
        return _rule(family, params), _rule(family, params), filters

    return build


def _pair_builder(long_family: str, short_family: str, axis_key: str,
                  long_fixed: dict, short_fixed: dict,
                  filters: tuple[dict, ...] = ()) -> Callable[[float, str], tuple[dict, dict, tuple[dict, ...]]]:
    def build(axis: float, tf: str) -> tuple[dict, dict, tuple[dict, ...]]:
        long_rule = _rule(long_family, {**long_fixed, axis_key: _coerce_param(axis_key, axis)})
        short_rule = _rule(short_family, dict(short_fixed))
        return long_rule, short_rule, filters

    return build


def _filter_builder(base_long: tuple[str, dict], base_short: tuple[str, dict],
                    axis_name: str, filters_fn: Callable[[float, str], tuple[dict, ...]]
                    ) -> Callable[[float, str], tuple[dict, dict, tuple[dict, ...]]]:
    def build(axis: float, tf: str) -> tuple[dict, dict, tuple[dict, ...]]:
        return _rule(*base_long), _rule(*base_short), filters_fn(axis, tf)

    return build


def _slow_ma_filter(axis: float, tf: str) -> tuple[dict, ...]:
    return (_filter("slow_ma_regime", {"period": _coerce_param("period", axis)}),)


def _atr_band_filter(axis: float, tf: str) -> tuple[dict, ...]:
    low = round(axis, 3)
    high = round(1.0 - axis, 3)
    return (_filter("atr_band", {"window": 96, "low": low, "high": high,
                                 "atr_period": _ATR_PERIOD}),)


def _funding_filter(axis: float, tf: str) -> tuple[dict, ...]:
    return (_filter("funding_extreme", {"thr": axis}),)


def _oi_macro_filter(axis: float, tf: str) -> tuple[dict, ...]:
    return (_filter("oi_momentum", {"window": 180, "lookback": 6, "z_thr": axis}),
            _filter("macro_regime", {"regime": "R1"}))


_TEMPLATES: tuple[_TemplateSpec, ...] = (
    _TemplateSpec(
        name="core_donchian_break",
        axis_name="n",
        axis_values=(20.0, 55.0, 100.0),
        exit_name="atr_trail",
        h=48,
        build=_core_builder("donchian_break", "n", {}),
    ),
    _TemplateSpec(
        name="core_atr_channel_break",
        axis_name="k",
        axis_values=(1.0, 1.5, 2.0),
        exit_name="chandelier",
        h=48,
        build=_core_builder("atr_channel_break", "k", {"atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="core_ma_cross",
        axis_name="slow",
        axis_values=(50.0, 100.0, 200.0),
        exit_name="donchian_trail",
        h=48,
        build=_core_builder("ma_cross", "slow", {"fast": 20}),
    ),
    _TemplateSpec(
        name="core_price_vs_ma",
        axis_name="period",
        axis_values=(50.0, 100.0, 200.0),
        exit_name="atr_trail",
        h=48,
        build=_core_builder("price_vs_ma", "period", {}),
    ),
    _TemplateSpec(
        name="core_roc_sign",
        axis_name="period",
        axis_values=(12.0, 24.0, 48.0),
        exit_name="chandelier",
        h=24,
        build=_core_builder("roc_sign", "period", {}),
    ),
    _TemplateSpec(
        name="core_reversion_in_range",
        axis_name="period",
        axis_values=(10.0, 14.0, 21.0),
        exit_name="fixed_bracket",
        h=24,
        build=_core_builder("reversion_in_range", "period", {"low": 25, "high": 75}),
    ),
    _TemplateSpec(
        name="core_vol_expansion",
        axis_name="mult",
        axis_values=(1.5, 2.0, 2.5),
        exit_name="atr_trail",
        h=24,
        build=_core_builder("vol_expansion", "mult", {"lookback": 24, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="core_vol_compression_breakout",
        axis_name="squeeze_n",
        axis_values=(16.0, 24.0, 32.0),
        exit_name="donchian_trail",
        h=48,
        build=_core_builder("vol_compression_breakout", "squeeze_n",
                            {"k": 1.0, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="pair_donchian_reversion",
        axis_name="n",
        axis_values=(20.0, 55.0, 100.0),
        exit_name="atr_trail",
        h=48,
        build=_pair_builder("donchian_break", "reversion_in_range", "n",
                            {}, {"period": 14, "low": 25, "high": 75}),
    ),
    _TemplateSpec(
        name="pair_donchian_atr",
        axis_name="n",
        axis_values=(20.0, 55.0, 100.0),
        exit_name="chandelier",
        h=48,
        build=_pair_builder("donchian_break", "atr_channel_break", "n",
                            {}, {"k": 1.5, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="pair_ma_price",
        axis_name="slow",
        axis_values=(50.0, 100.0, 200.0),
        exit_name="donchian_trail",
        h=48,
        build=_pair_builder("ma_cross", "price_vs_ma", "slow",
                            {"fast": 20}, {"period": 100}),
    ),
    _TemplateSpec(
        name="pair_price_roc",
        axis_name="period",
        axis_values=(50.0, 100.0, 200.0),
        exit_name="atr_trail",
        h=48,
        build=_pair_builder("price_vs_ma", "roc_sign", "period",
                            {}, {"period": 24}),
    ),
    _TemplateSpec(
        name="pair_roc_volexp",
        axis_name="period",
        axis_values=(12.0, 24.0, 48.0),
        exit_name="chandelier",
        h=24,
        build=_pair_builder("roc_sign", "vol_expansion", "period",
                            {}, {"lookback": 24, "mult": 2.0, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="pair_atr_reversion",
        axis_name="k",
        axis_values=(1.0, 1.5, 2.0),
        exit_name="atr_trail",
        h=48,
        build=_pair_builder("atr_channel_break", "reversion_in_range", "k",
                            {"atr_period": _ATR_PERIOD},
                            {"period": 14, "low": 25, "high": 75}),
    ),
    _TemplateSpec(
        name="pair_vexp_vcomp",
        axis_name="mult",
        axis_values=(1.5, 2.0, 2.5),
        exit_name="atr_trail",
        h=24,
        build=_pair_builder("vol_expansion", "vol_compression_breakout", "mult",
                            {"lookback": 24, "atr_period": _ATR_PERIOD},
                            {"squeeze_n": 24, "k": 1.0, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="pair_vcomp_atr",
        axis_name="squeeze_n",
        axis_values=(16.0, 24.0, 32.0),
        exit_name="donchian_trail",
        h=48,
        build=_pair_builder("vol_compression_breakout", "atr_channel_break", "squeeze_n",
                            {"k": 1.0, "atr_period": _ATR_PERIOD},
                            {"k": 1.5, "atr_period": _ATR_PERIOD}),
    ),
    _TemplateSpec(
        name="filter_slow_ma",
        axis_name="period",
        axis_values=(100.0, 150.0, 200.0),
        exit_name="atr_trail",
        h=48,
        build=_filter_builder(
            ("donchian_break", {"n": 55}),
            ("donchian_break", {"n": 55}),
            "period",
            _slow_ma_filter,
        ),
    ),
    _TemplateSpec(
        name="filter_atr_band",
        axis_name="q",
        axis_values=(0.20, 0.30, 0.40),
        exit_name="chandelier",
        h=48,
        build=_filter_builder(
            ("atr_channel_break", {"k": 1.5, "atr_period": _ATR_PERIOD}),
            ("atr_channel_break", {"k": 1.5, "atr_period": _ATR_PERIOD}),
            "q",
            _atr_band_filter,
        ),
    ),
    _TemplateSpec(
        name="filter_funding_extreme",
        axis_name="thr",
        axis_values=(0.00010, 0.00020, 0.00030),
        exit_name="donchian_trail",
        h=48,
        build=_filter_builder(
            ("ma_cross", {"fast": 20, "slow": 100}),
            ("price_vs_ma", {"period": 100}),
            "thr",
            _funding_filter,
        ),
    ),
    _TemplateSpec(
        name="filter_oi_macro",
        axis_name="z_thr",
        axis_values=(1.0, 1.5, 2.0),
        exit_name="atr_trail",
        h=48,
        build=_filter_builder(
            ("price_vs_ma", {"period": 100}),
            ("donchian_break", {"n": 55}),
            "z_thr",
            _oi_macro_filter,
        ),
    ),
)


def _instantiate(tf: str, spec: _TemplateSpec, axis: float) -> ExploreConfig:
    long_rule, short_rule, filters = spec.build(axis, tf)
    exit_params = dict(_TREND_EXIT[tf].get(spec.exit_name, _MR_EXIT[tf].get(spec.exit_name, {})))
    if spec.exit_name == "fixed_bracket":
        exit_params = dict(_MR_EXIT[tf]["fixed_bracket"])
    group = _group(tf, spec.name, long_rule, short_rule, filters, spec.exit_name, exit_params,
                   spec.axis_name)
    label = _label(tf, spec.name, spec.axis_name, axis, long_rule, short_rule,
                   filters, spec.exit_name, exit_params)
    return ExploreConfig(
        label=label,
        timeframe=tf,
        long_rule=long_rule,
        short_rule=short_rule,
        filters=filters,
        exit_name=spec.exit_name,
        exit_params=exit_params,
        h=spec.h,
        group=group,
        axis=float(axis),
    )


def configs_for(timeframe: str) -> list[ExploreConfig]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    out: list[ExploreConfig] = []
    for spec in _TEMPLATES:
        for axis in spec.axis_values:
            out.append(_instantiate(timeframe, spec, axis))
    return out


def all_configs(timeframes: tuple[str, ...] = TIMEFRAMES) -> list[ExploreConfig]:
    out: list[ExploreConfig] = []
    for tf in timeframes:
        out.extend(configs_for(tf))
    return out


def config_doc(timeframes: tuple[str, ...] = TIMEFRAMES) -> list[dict]:
    return [asdict(cfg) for cfg in all_configs(timeframes)]
