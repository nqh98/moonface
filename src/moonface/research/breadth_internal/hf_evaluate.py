from __future__ import annotations

from collections.abc import Callable

from moonface.research.breadth.evaluate import score_records, summarize
from moonface.research.breadth.signals import _ALWAYS
from moonface.research.breadth_internal.grid import SignalSpec
from moonface.research.breadth_internal.hf_signals import (
    breadth_accel_state,
    breadth_momentum_state,
    breadth_oscillator_state,
)
from moonface.research.breadth_internal.overlap import overlapping_entries_from_state


def _oscillator(daily, btc, params, is_member):
    return breadth_oscillator_state(
        daily, int(params["window"]), params["z_in"],
        int(params["base_period"]), is_member=is_member)


def _momentum(daily, btc, params, is_member):
    return breadth_momentum_state(
        daily, int(params["n"]), params["thr"],
        int(params["base_period"]), is_member=is_member)


def _accel(daily, btc, params, is_member):
    return breadth_accel_state(
        daily, int(params["n"]), params["thr"],
        int(params["base_period"]), is_member=is_member)


HF_BUILDERS = {
    "breadth_oscillator": _oscillator,
    "breadth_momentum": _momentum,
    "breadth_accel": _accel,
}


def _state(daily, btc, spec: SignalSpec, is_member):
    try:
        builder = HF_BUILDERS[spec.builder]
    except KeyError as exc:
        raise ValueError(f"unknown hf builder {spec.builder!r}") from exc
    return builder(daily, btc, spec.params, is_member)


def hf_cell_entries(
    daily,
    btc,
    spec: SignalSpec,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> list[tuple[int, str]]:
    if not daily or not btc:
        return []
    return overlapping_entries_from_state(btc, _state(daily, btc, spec, is_member), spec.h)


def evaluate_hf_spec(
    daily,
    btc,
    spec: SignalSpec,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    entries = hf_cell_entries(daily, btc, spec, is_member)
    records = score_records(btc, entries, spec.exit_name, spec.exit_params)
    return {"key": spec.key, "metrics": summarize(records), "records": records}
