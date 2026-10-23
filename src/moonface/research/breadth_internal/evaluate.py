from __future__ import annotations

from collections.abc import Callable

from moonface.research.breadth.evaluate import score_records, summarize
from moonface.research.breadth.signals import (
    _ALWAYS,
    entries_from_state,
    pct_above_ma_series,
    thrust_state,
)
from moonface.research.breadth_internal.grid import SignalSpec
from moonface.research.breadth_internal.signals import (
    breadth_divergence_state,
    dispersion_regime_state,
    net_new_highs_state,
)


def _breadth_thrust_state(daily, btc, params, is_member):
    series = pct_above_ma_series(
        daily,
        int(params["base_period"]),
        is_member=is_member,
    )
    return thrust_state(
        series,
        params["low_band"],
        params["high_band"],
        int(params["window"]),
    )


def _net_new_highs_state(daily, btc, params, is_member):
    return net_new_highs_state(
        daily,
        int(params["n"]),
        params["long_thr"],
        params["short_thr"],
        is_member=is_member,
    )


def _breadth_divergence_state(daily, btc, params, is_member):
    return breadth_divergence_state(
        daily,
        btc,
        int(params["n"]),
        int(params["base_period"]),
        is_member=is_member,
    )


def _dispersion_regime_state(daily, btc, params, is_member):
    return dispersion_regime_state(
        daily,
        btc,
        int(params["d"]),
        int(params["m_ma"]),
        int(params["window"]),
        params["p"],
        is_member=is_member,
    )


_BUILDERS = {
    "breadth_thrust": _breadth_thrust_state,
    "net_new_highs": _net_new_highs_state,
    "breadth_divergence": _breadth_divergence_state,
    "dispersion_regime": _dispersion_regime_state,
}


def _state(daily, btc, spec: SignalSpec, is_member):
    try:
        builder = _BUILDERS[spec.builder]
    except KeyError as exc:
        raise ValueError(f"unknown builder {spec.builder!r}") from exc
    return builder(daily, btc, spec.params, is_member)


def cell_entries(
    daily,
    btc,
    spec: SignalSpec,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> list[tuple[int, str]]:
    if not daily or not btc:
        return []
    return entries_from_state(btc, _state(daily, btc, spec, is_member), spec.h)


def evaluate_spec(
    daily,
    btc,
    spec: SignalSpec,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    entries = cell_entries(daily, btc, spec, is_member)
    records = score_records(btc, entries, spec.exit_name, spec.exit_params)
    return {"key": spec.key, "metrics": summarize(records), "records": records}
