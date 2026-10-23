from __future__ import annotations

import json
from collections.abc import Callable

from moonface.research.breadth.evaluate import score_records, summarize
from moonface.research.breadth.signals import _ALWAYS, entries_from_state
from moonface.research.breadth_internal.evaluate import _BUILDERS as L1_BUILDERS
from moonface.research.breadth_internal.hf_evaluate import HF_BUILDERS

_ALL_BUILDERS = {**L1_BUILDERS, **HF_BUILDERS}

_VOTE = {"LONG": 1, "SHORT": -1, "FLAT": 0}


def load_survivors(result_paths: list[str]) -> list[dict]:
    survivors: list[dict] = []
    for path in result_paths:
        with open(path) as f:
            doc = json.load(f)
        sealed_end = doc.get("windows", {}).get("sealed", [None, None])[1]
        for row in doc.get("rows", []):
            if row.get("verdict") == "forward_candidate":
                survivors.append({"spec": row["spec"], "sealed_end": sealed_end})
    return survivors


def member_state(daily, btc, spec: dict, is_member=_ALWAYS) -> list[tuple[int, str]]:
    builder = _ALL_BUILDERS.get(spec["builder"])
    if builder is None:
        raise ValueError(f"unknown member builder {spec['builder']!r}")
    # builders accept a MappingProxy or dict; pass the plain params dict.
    return builder(daily, btc, spec["params"], is_member)


def net_vote_state(member_states: list[list[tuple[int, str]]]) -> list[tuple[int, str]]:
    if not member_states:
        return []
    maps = [dict(ms) for ms in member_states]
    shared = set(maps[0])
    for m in maps[1:]:
        shared &= set(m)
    out: list[tuple[int, str]] = []
    for ts in sorted(shared):
        score = sum(_VOTE[m[ts]] for m in maps)
        side = "LONG" if score > 0 else "SHORT" if score < 0 else "FLAT"
        out.append((ts, side))
    return out


def evaluate_ensemble(
    daily, btc, specs: list[dict],
    is_member: Callable[[str, int], bool] = _ALWAYS,
) -> dict:
    states = [member_state(daily, btc, s, is_member) for s in specs]
    state = net_vote_state(states)
    h = specs[0]["h"] if specs else 48
    entries = entries_from_state(btc, state, h)
    exit_name = specs[0]["exit_name"] if specs else "atr_trail"
    exit_params = specs[0]["exit_params"] if specs else {}
    records = score_records(btc, entries, exit_name, exit_params)
    return {"metrics": summarize(records), "records": records, "state": state}
