"""Stage 2 — practical candidate selection for the BTC-Specialized lane. A wide
explore grid is reduced to the top-K configs per family by net total R, among configs
that are NOT a lone parameter-island spike. All out-of-sample economic gates live in
the validator (validate.py); selection only ranks + de-spikes on explore metrics."""
from __future__ import annotations

TOP_K = 3
ISLAND_PF = 1.0  # a neighbour need only be non-catastrophic (break-even+) to anchor


def island_ok(row, rows_by_group) -> bool:
    members = sorted(rows_by_group[row["group"]], key=lambda r: r["axis"])
    idx = next(k for k, r in enumerate(members) if r["label"] == row["label"])
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(members) and members[j]["metrics"]["profit_factor"] >= ISLAND_PF:
            return True
    return False


def select(explore_rows) -> list[dict]:
    by_group: dict[str, list] = {}
    for r in explore_rows:
        by_group.setdefault(r["group"], []).append(r)
    passers = [r for r in explore_rows if island_ok(r, by_group)]
    survivors: list[dict] = []
    for family in sorted({r["family"] for r in passers}):
        fam_rows = sorted((r for r in passers if r["family"] == family),
                          key=lambda r: r["metrics"]["total_r"], reverse=True)
        for r in fam_rows[:TOP_K]:
            survivors.append({**r, "selection": {"island": True, "passed": True}})
    return survivors
