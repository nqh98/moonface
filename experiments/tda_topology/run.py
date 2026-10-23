"""tda_topology_v1 -- offline orchestrator.

NOT A GATE. Emits no pass/fail for any trading decision. See
docs/research-log/specs/2026-07-16-tda-topology-design.md."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from moonface.research.microscope.events import (HORIZONS, bucket_report,
                                                 event_outcomes,
                                                 null_calibration)
from moonface.research.microscope.events import Event
from moonface.research.microscope.regimes import UNLABELED

from grid import UNIVERSE, build_grid, load_pool_cache_only, log_return_matrix
from nulls import block_null_calibration
from tda_features import FEATURE_KEYS, build_features
from tda_labels import build_labels

# Published microscope result on this same 1838-event set (extended window),
# for the head-to-head. See memory: market-state-microscope-lane.
MICROSCOPE_BASELINE = {"real_effect": 0.609, "null_p95": 0.835,
                       "verdict": "INDISTINGUISHABLE_FROM_NULL"}


def parse_events_csv(path: Path) -> list[Event]:
    with path.open() as fh:
        return [Event(ts_ms=int(r["ts_ms"]), symbol=r["symbol"],
                      direction=int(r["direction"]))
                for r in csv.DictReader(fh)]


def write_csv(path: Path, rows: list[dict], header: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_study(pool, events: list[Event], timestamps: list[int],
              seed: int) -> dict:
    returns = log_return_matrix(pool, timestamps)
    features = build_features(returns, n_bars=len(timestamps))
    bar_labels = build_labels(features)
    # The label is market-level: one value per bar, broadcast to every symbol.
    labels = {sym: list(bar_labels) for sym in pool}
    outcomes = event_outcomes(pool, labels, timestamps, events)
    return {"features": features,
            "bar_labels": bar_labels,
            "outcomes": outcomes,
            "buckets": bucket_report(outcomes, seed=seed),
            "block_null": block_null_calibration(outcomes, bar_labels,
                                                 timestamps, seed=seed),
            "row_null": null_calibration(outcomes, seed=seed)}


def render_report(res: dict, n_events: int) -> str:
    outcomes = res["outcomes"]
    n_unlabeled = sum(1 for r in outcomes if r["label"] == UNLABELED)
    block, row = res["block_null"], res["row_null"]
    lines = [
        "# tda_topology_v1 -- correlation topology conditional study",
        "",
        "**NOT A GATE.** Descriptive instrument. No lockbox, no DSR ladder, "
        "no promotion path. A verdict here is about whether topology *sees* "
        "anything, not about whether anything is tradeable.",
        "",
        f"- events supplied: {n_events}",
        f"- events usable: {len(outcomes)}",
        f"- UNLABELED: {n_unlabeled}",
        f"- distinct bars: {len(set(r['ts_ms'] for r in outcomes))}",
        "",
        "## Verdict (primary: block-permutation null)",
        "",
        f"**{block['verdict']}** -- real effect {block['real_effect']} vs "
        f"null p95 {block['null_p95']} (beaten {block['pct_beaten']:.0%})",
        "",
        "## Secondary diagnostic: row-wise null",
        "",
        f"{row['verdict']} -- real effect {row['real_effect']} vs null p95 "
        f"{row['null_p95']}. The row null ignores the label series' "
        "autocorrelation and is therefore easier to beat; the gap between "
        "these two numbers is the reason the block null is primary.",
        "",
        "## Head-to-head: Market State Microscope, same 1838 events",
        "",
        "| | real effect | null p95 | verdict |",
        "|---|---:|---:|---|",
        f"| microscope 5-factor | {MICROSCOPE_BASELINE['real_effect']} | "
        f"{MICROSCOPE_BASELINE['null_p95']} | "
        f"{MICROSCOPE_BASELINE['verdict']} |",
        f"| tda block null | {block['real_effect']} | {block['null_p95']} | "
        f"{block['verdict']} |",
        "",
        "## Scope caveat",
        "",
        "All supplied events are **long-only** trend-breakout entries, so "
        "they fire mainly in UP-ish regimes: RANGE is thin and DOWN is "
        "absent. A negative verdict closes the geometric axis for long "
        "trend-breakout entries -- the same scope the microscope finding has. "
        "A long+short event source would be a different lane.",
        "",
        "## Buckets",
        "",
        "| label | n | verdict | " +
        " | ".join(f"fwd_r_{h} mean" for h in HORIZONS) + " |",
        "|---|---:|---|" + "---:|" * len(HORIZONS),
    ]
    for b in res["buckets"]:
        cells = [str(b.get(f"fwd_r_{h}_mean", "-")) for h in HORIZONS]
        lines.append(f"| {b['label']} | {b['n']} | {b['verdict']} | "
                     + " | ".join(cells) + " |")
    lines += ["",
              "Buckets below POWER_FLOOR=30 report their size and nothing "
              "else -- no direction, no CI."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tda_topology", description=__doc__)
    p.add_argument("--cache-dir", default="../../cache/matrix")
    p.add_argument("--events", required=True)
    p.add_argument("--out", default=".")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pool = load_pool_cache_only(args.cache_dir, UNIVERSE)
    timestamps = build_grid(pool)
    events = parse_events_csv(Path(args.events))
    res = run_study(pool, events, timestamps, seed=args.seed)

    write_csv(out_dir / "features.csv",
              [{"ts_ms": ts, **res["features"][t]}
               for t, ts in enumerate(timestamps)],
              ["ts_ms", *FEATURE_KEYS])
    write_csv(out_dir / "labels.csv",
              [{"ts_ms": ts, "label": res["bar_labels"][t]}
               for t, ts in enumerate(timestamps)],
              ["ts_ms", "label"])
    write_csv(out_dir / "outcomes.csv", res["outcomes"],
              ["symbol", "ts_ms", "direction", "label",
               *[f"fwd_r_{h}" for h in HORIZONS],
               "mfe_r", "mae_r", "stop_first", "fwd_vol"])
    text = render_report(res, n_events=len(events))
    (out_dir / "report.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
