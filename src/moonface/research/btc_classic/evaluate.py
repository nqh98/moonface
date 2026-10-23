from __future__ import annotations

from moonface.research.breadth.evaluate import score_records, summarize
from moonface.research.btc_classic.grid import SignalSpec
from moonface.research.edge import signals as price_signals
from moonface.research.edge.funding_signals import make_funding_fade


def cell_entries(btc, funding, spec: SignalSpec) -> list[tuple[int, str]]:
    if not btc:
        return []
    if spec.kind == "price":
        builder = getattr(price_signals, spec.builder)
        return builder(btc, dict(spec.params))
    if spec.kind == "funding":
        if not funding:
            return []
        gen = make_funding_fade(funding)
        return gen(btc, dict(spec.params))
    raise ValueError(f"unknown spec kind {spec.kind!r}")


def evaluate_spec(btc, funding, spec: SignalSpec) -> dict:
    entries = cell_entries(btc, funding, spec)
    records = score_records(btc, entries, spec.exit_name, dict(spec.exit_params))
    return {"key": spec.key, "metrics": summarize(records), "records": records}
