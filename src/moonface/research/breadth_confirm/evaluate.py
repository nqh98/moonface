from __future__ import annotations

from collections.abc import Callable

from moonface.research.breadth.evaluate import score_records, summarize
from moonface.research.breadth.signals import _ALWAYS
from moonface.research.breadth_confirm.grid import SignalSpec
from moonface.research.breadth_internal.overlap import overlapping_entries_from_state
from moonface.research.breadth_internal.signals import net_new_highs_state


def evaluate_slice_overlap(
    daily,
    btc,
    spec: SignalSpec,
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    """Frozen net_new_highs state on `daily` -> overlapping BTC entries on the
    windowed `btc` candles -> scored net-R records + summary. Overlapping
    (one entry per active day) recovers the events the h=48 non-overlap mapping
    discards; the autocorrelation is corrected downstream by the block bootstrap."""
    if not daily or not btc:
        return {"key": spec.key, "metrics": summarize([]), "records": []}
    state = net_new_highs_state(
        daily,
        int(spec.params["n"]),
        spec.params["long_thr"],
        spec.params["short_thr"],
        is_member=is_member,
    )
    entries = overlapping_entries_from_state(btc, state, spec.h)
    records = score_records(btc, entries, spec.exit_name, spec.exit_params)
    return {"key": spec.key, "metrics": summarize(records), "records": records}
