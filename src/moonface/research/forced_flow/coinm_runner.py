"""One-cycle terminal runner for the approved COIN-M forced-flow pilot."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Sequence

from moonface.research.forced_flow.coinm_archive import load_coinm_bars
from moonface.research.forced_flow.iid_guard import (
    FROZEN,
    NullBatteryResult,
    run_null_battery,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
VERDICT_DIR = PROJECT_ROOT / "experiments" / "forced_flow"
VERDICT_JSON = "verdict.json"
VERDICT_MARKDOWN = "PILOT_VERDICT.md"


@dataclass(frozen=True)
class PilotVerdict:
    verdict: str
    episode_count: int
    qualifying_bucket_count: int
    observed_spread: float | None
    label_shuffle_p975: float | None
    circular_shift_p975: float | None
    iid_guard_passed: bool
    label_shuffle_discarded_draws: int
    circular_shift_discarded_draws: int
    iid_return_discarded_draws: int
    split_half_first: str
    split_half_second: str


def run_once(archive_root: Path) -> PilotVerdict:
    """Run the frozen pilot once and write its two terminal artifacts.

    A completed or partially completed verdict directory is intentionally terminal.
    """
    json_path = VERDICT_DIR / VERDICT_JSON
    markdown_path = VERDICT_DIR / VERDICT_MARKDOWN
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError("COIN-M pilot verdict already exists; a second cycle is forbidden")
    bars = load_coinm_bars(archive_root)
    battery = run_null_battery(
        bars.closes, bars.liq_counts, bars.liq_imbalances, segments=bars.segments
    )
    verdict = _build_verdict(battery, bars.timestamps)
    _write_verdict_once(verdict, json_path, markdown_path)
    return verdict


def _build_verdict(
    battery: NullBatteryResult, timestamps: Sequence[datetime]
) -> PilotVerdict:
    return PilotVerdict(
        verdict=_select_verdict(battery),
        episode_count=len(battery.pipeline.episodes),
        qualifying_bucket_count=len(battery.pipeline.qualifying_buckets),
        observed_spread=battery.pipeline.spread,
        label_shuffle_p975=battery.label_shuffle.threshold_p975,
        circular_shift_p975=battery.circular_shift.threshold_p975,
        iid_guard_passed=battery.iid_return.passed,
        label_shuffle_discarded_draws=battery.label_shuffle.discarded_draws,
        circular_shift_discarded_draws=battery.circular_shift.discarded_draws,
        iid_return_discarded_draws=battery.iid_return.discarded_draws,
        split_half_first=_split_half_consistency(battery.pipeline, timestamps)[0],
        split_half_second=_split_half_consistency(battery.pipeline, timestamps)[1],
    )


def _split_half_consistency(pipeline, timestamps: Sequence[datetime]) -> tuple[str, str]:
    if len(pipeline.qualifying_buckets) < 2:
        return ("NOT_EVALUABLE", "NOT_EVALUABLE")
    ranked = sorted(
        enumerate(pipeline.episodes), key=lambda item: (item[1].burst_z, item[1].bar_index)
    )
    terciles = {
        episode_index: min(2, 3 * rank // len(ranked))
        for rank, (episode_index, _) in enumerate(ranked)
    }
    bottom = min(
        pipeline.qualifying_buckets,
        key=lambda bucket: (bucket.mean_outcome, bucket.direction, bucket.tercile),
    )
    top = max(
        pipeline.qualifying_buckets,
        key=lambda bucket: (bucket.mean_outcome, bucket.direction, bucket.tercile),
    )
    bucket_keys = {
        "bottom": (bottom.direction, bottom.tercile),
        "top": (top.direction, top.tercile),
    }
    boundary = datetime(2024, 2, 16, tzinfo=UTC)
    halves = (
        (datetime(2023, 6, 25, tzinfo=UTC), boundary),
        (boundary, datetime(2024, 10, 15, tzinfo=UTC)),
    )
    results: list[str] = []
    for start, end in halves:
        values = {"bottom": [], "top": []}
        for index, episode in enumerate(pipeline.episodes):
            timestamp = timestamps[episode.bar_index]
            if start <= timestamp < end:
                key = (episode.direction, terciles[index])
                for label, bucket_key in bucket_keys.items():
                    if key == bucket_key:
                        values[label].append(episode.outcome)
        if any(len(values[label]) < 10 for label in values):
            results.append("NOT_EVALUABLE")
        else:
            results.append(
                "POSITIVE"
                if sum(values["top"]) / len(values["top"])
                > sum(values["bottom"]) / len(values["bottom"])
                else "NOT_POSITIVE"
            )
    return tuple(results)  # type: ignore[return-value]


def _select_verdict(battery: NullBatteryResult) -> str:
    """Apply the registration's terminal precedence without adding a new gate."""
    if (
        battery.iid_return.passed
        or battery.label_shuffle.discarded_draws > FROZEN.null_draws / 2
        or battery.circular_shift.discarded_draws > FROZEN.null_draws / 2
        or battery.iid_return.discarded_draws > FROZEN.null_draws / 2
    ):
        return "SUSPECT_HARNESS"
    if len(battery.pipeline.qualifying_buckets) < 2:
        return "UNDERPOWERED_KILL"
    if not battery.label_shuffle.passed or not battery.circular_shift.passed:
        return "KILL"
    return "WEAK SUPPORT"


def _write_verdict_once(verdict: PilotVerdict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(verdict), indent=2, sort_keys=True) + "\n"
    markdown = _render_markdown(verdict)
    for path, contents in ((json_path, payload), (markdown_path, markdown)):
        with path.open("x", encoding="utf-8", newline="") as output:
            output.write(contents)


def _render_markdown(verdict: PilotVerdict) -> str:
    return "\n".join(
        (
            "# COIN-M Pilot Verdict",
            "",
            f"**Verdict:** {verdict.verdict}",
            "",
            "| Measure | Value |",
            "|---|---:|",
            f"| Episode count | {verdict.episode_count} |",
            f"| Qualifying bucket count | {verdict.qualifying_bucket_count} |",
            f"| Observed spread | {_format_number(verdict.observed_spread)} |",
            f"| Label-shuffle p97.5 | {_format_number(verdict.label_shuffle_p975)} |",
            f"| Circular-shift p97.5 | {_format_number(verdict.circular_shift_p975)} |",
            f"| iid guard passed | {str(verdict.iid_guard_passed).lower()} |",
            f"| Label-shuffle discarded draws | {verdict.label_shuffle_discarded_draws} |",
            f"| Circular-shift discarded draws | {verdict.circular_shift_discarded_draws} |",
            f"| iid-return discarded draws | {verdict.iid_return_discarded_draws} |",
            f"| Split-half consistency | {verdict.split_half_first} / {verdict.split_half_second} |",
            "",
        )
    )


def _format_number(value: float | None) -> str:
    return "null" if value is None else format(value, ".12g")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen COIN-M forced-flow pilot once.")
    parser.add_argument("archive_root", type=Path, help="Downloaded Binance Vision COIN-M ZIP root")
    args = parser.parse_args(argv)
    run_once(args.archive_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
