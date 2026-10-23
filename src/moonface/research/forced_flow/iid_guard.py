"""Frozen, pure-stdlib null calibration for the approved COIN-M pilot.

This module deliberately accepts already-loaded bar data only.  It contains no
network, archive, CLI, or engine integration surface.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence


@dataclass(frozen=True)
class FrozenParameters:
    bar_hours: int = 1
    z_window_bars: int = 720
    min_history_bars: int = 240
    entry_threshold: float = 2.0
    rearm_bars: int = 6
    horizon_bars: int = 24
    power_floor: int = 30
    null_draws: int = 1_000
    seed: int = 1337


FROZEN = FrozenParameters()


@dataclass(frozen=True)
class Segment:
    """A chronological, contiguous run of retained hourly bars."""

    start: int
    stop: int
    starts_after_gap: bool


@dataclass(frozen=True)
class Episode:
    bar_index: int
    direction: int
    burst_z: float
    outcome: float


@dataclass(frozen=True)
class Bucket:
    direction: int
    tercile: int
    outcomes: tuple[float, ...]
    mean_outcome: float


@dataclass(frozen=True)
class PipelineResult:
    episodes: tuple[Episode, ...]
    qualifying_buckets: tuple[Bucket, ...]
    spread: float | None


@dataclass(frozen=True)
class NullResult:
    observed_spread: float | None
    threshold_p975: float | None
    passed: bool
    null_spreads: tuple[float, ...]
    discarded_draws: int = 0


@dataclass(frozen=True)
class NullBatteryResult:
    pipeline: PipelineResult
    label_shuffle: NullResult
    circular_shift: NullResult
    iid_return: NullResult


def build_pipeline(
    closes: Sequence[float],
    liq_counts: Sequence[int],
    liq_imbalances: Sequence[float],
    *,
    segments: Sequence[Segment] | None = None,
) -> PipelineResult:
    """Build frozen episodes, direction×tercile buckets, and the spread."""
    _validate_inputs(closes, liq_counts, liq_imbalances)
    normalized_segments = _normalize_segments(len(closes), segments)
    episodes: list[Episode] = []
    for segment in normalized_segments:
        if segment.stop - segment.start < 2 * FROZEN.z_window_bars:
            continue
        burst_z = _causal_burst_z(liq_counts[segment.start : segment.stop])
        consecutive_below = 0
        minimum_entry_history = (
            FROZEN.z_window_bars if segment.starts_after_gap else FROZEN.min_history_bars
        )
        for local_index, z_score in enumerate(burst_z):
            bar_index = segment.start + local_index
            if z_score is None:
                consecutive_below = 0
                continue
            if z_score < FROZEN.entry_threshold:
                consecutive_below += 1
                continue
            if consecutive_below >= FROZEN.rearm_bars and local_index >= minimum_entry_history:
                direction = _sign(liq_imbalances[bar_index])
                if direction and local_index + FROZEN.horizon_bars < segment.stop - segment.start:
                    outcome = math.log(
                        closes[bar_index + FROZEN.horizon_bars] / closes[bar_index]
                    )
                    episodes.append(Episode(bar_index, direction, z_score, outcome))
            consecutive_below = 0
    qualifying_buckets = _qualifying_buckets(episodes)
    spread = _spread(qualifying_buckets)
    return PipelineResult(tuple(episodes), qualifying_buckets, spread)


def label_shuffle_null(pipeline: PipelineResult) -> NullResult:
    """Permute episode outcomes 1,000 times while preserving all bucket labels."""
    if pipeline.spread is None:
        return _empty_null(pipeline.spread)
    rng = _null_rng("label")
    outcomes = [episode.outcome for episode in pipeline.episodes]
    null_spreads: list[float] = []
    discarded_draws = 0
    for _ in range(FROZEN.null_draws):
        rng.shuffle(outcomes)
        spread = _spread(_qualifying_buckets(pipeline.episodes, outcomes))
        if spread is not None:
            null_spreads.append(spread)
        else:
            discarded_draws += 1
    return _finish_null(pipeline.spread, null_spreads, discarded_draws=discarded_draws)


def circular_shift_null(
    closes: Sequence[float],
    liq_counts: Sequence[int],
    liq_imbalances: Sequence[float],
    observed_spread: float | None,
    *,
    segments: Sequence[Segment] | None = None,
) -> NullResult:
    """Shift both liquidation feature series by at least 30 days against price."""
    if observed_spread is None:
        return _empty_null(observed_spread)
    normalized_segments = _normalize_segments(len(closes), segments)
    rng = _null_rng("circular")
    null_spreads: list[float] = []
    discarded_draws = 0
    for _ in range(FROZEN.null_draws):
        shifted_counts = list(liq_counts)
        shifted_imbalances = list(liq_imbalances)
        for segment in normalized_segments:
            segment_length = segment.stop - segment.start
            if segment_length < 2 * FROZEN.z_window_bars:
                continue
            offset = rng.randint(FROZEN.z_window_bars, segment_length - FROZEN.z_window_bars)
            shifted_counts[segment.start : segment.stop] = _circular_shift(
                liq_counts[segment.start : segment.stop], offset
            )
            shifted_imbalances[segment.start : segment.stop] = _circular_shift(
                liq_imbalances[segment.start : segment.stop], offset
            )
        spread = build_pipeline(
            closes, shifted_counts, shifted_imbalances, segments=normalized_segments
        ).spread
        if spread is not None:
            null_spreads.append(spread)
        else:
            discarded_draws += 1
    return _finish_null(observed_spread, null_spreads, discarded_draws=discarded_draws)


def iid_return_null(
    closes: Sequence[float],
    liq_counts: Sequence[int],
    liq_imbalances: Sequence[float],
    observed_spread: float | None,
    *,
    segments: Sequence[Segment] | None = None,
) -> NullResult:
    """Rebuild price paths from iid-resampled log returns and rerun the pipeline."""
    if observed_spread is None:
        return _empty_null(observed_spread)
    normalized_segments = _normalize_segments(len(closes), segments)
    rng = _null_rng("iid")
    null_spreads: list[float] = []
    discarded_draws = 0
    for _ in range(FROZEN.null_draws):
        rebuilt_closes = list(closes)
        for segment in normalized_segments:
            segment_closes = closes[segment.start : segment.stop]
            log_returns = [
                math.log(current / previous)
                for previous, current in zip(segment_closes, segment_closes[1:])
            ]
            rebuilt_closes[segment.start : segment.stop] = _rebuild_iid_price_path(
                segment_closes[0], log_returns, rng
            )
        spread = build_pipeline(
            rebuilt_closes, liq_counts, liq_imbalances, segments=normalized_segments
        ).spread
        if spread is not None:
            null_spreads.append(spread)
        else:
            discarded_draws += 1
    return _finish_null(observed_spread, null_spreads, discarded_draws=discarded_draws)


def run_null_battery(
    closes: Sequence[float],
    liq_counts: Sequence[int],
    liq_imbalances: Sequence[float],
    *,
    segments: Sequence[Segment] | None = None,
) -> NullBatteryResult:
    """Run the frozen pipeline and its three deterministic Gate-0 nulls."""
    normalized_segments = _normalize_segments(len(closes), segments)
    pipeline = build_pipeline(closes, liq_counts, liq_imbalances, segments=normalized_segments)
    return NullBatteryResult(
        pipeline=pipeline,
        label_shuffle=label_shuffle_null(pipeline),
        circular_shift=circular_shift_null(
            closes, liq_counts, liq_imbalances, pipeline.spread, segments=normalized_segments
        ),
        iid_return=iid_return_null(
            closes, liq_counts, liq_imbalances, pipeline.spread, segments=normalized_segments
        ),
    )


def _validate_inputs(
    closes: Sequence[float], liq_counts: Sequence[int], liq_imbalances: Sequence[float]
) -> None:
    if not closes or len(closes) != len(liq_counts) or len(closes) != len(liq_imbalances):
        raise ValueError("closes, liquidation counts, and imbalances must be equally sized")
    if any(close <= 0 for close in closes):
        raise ValueError("closes must be positive")
    if any(count < 0 for count in liq_counts):
        raise ValueError("liquidation counts cannot be negative")


def _causal_burst_z(liq_counts: Sequence[int]) -> list[float | None]:
    values = [math.log1p(count) for count in liq_counts]
    sums = [0.0]
    squared_sums = [0.0]
    for value in values:
        sums.append(sums[-1] + value)
        squared_sums.append(squared_sums[-1] + value * value)
    scores: list[float | None] = []
    for bar_index, value in enumerate(values):
        window_start = max(0, bar_index - FROZEN.z_window_bars)
        history_size = bar_index - window_start
        if history_size < FROZEN.min_history_bars:
            scores.append(None)
            continue
        mean = (sums[bar_index] - sums[window_start]) / history_size
        sum_squares = squared_sums[bar_index] - squared_sums[window_start]
        centered_sum_squares = max(0.0, sum_squares - history_size * mean * mean)
        variance = centered_sum_squares / (history_size - 1)
        if variance == 0.0:
            scores.append(None)
            continue
        scores.append((value - mean) / math.sqrt(variance))
    return scores


def _qualifying_buckets(
    episodes: Sequence[Episode], outcomes: Sequence[float] | None = None
) -> tuple[Bucket, ...]:
    if outcomes is not None and len(outcomes) != len(episodes):
        raise ValueError("outcomes length must match episodes")
    terciles = [0] * len(episodes)
    ranked = sorted(enumerate(episodes), key=lambda item: (item[1].burst_z, item[1].bar_index))
    for rank, (episode_index, _) in enumerate(ranked):
        terciles[episode_index] = min(2, 3 * rank // len(ranked)) if ranked else 0
    grouped: dict[tuple[int, int], list[float]] = {}
    for episode_index, episode in enumerate(episodes):
        outcome = episode.outcome if outcomes is None else outcomes[episode_index]
        grouped.setdefault((episode.direction, terciles[episode_index]), []).append(outcome)
    buckets = [
        Bucket(direction, tercile, tuple(values), sum(values) / len(values))
        for (direction, tercile), values in grouped.items()
        if len(values) >= FROZEN.power_floor
    ]
    return tuple(sorted(buckets, key=lambda bucket: (bucket.direction, bucket.tercile)))


def _spread(buckets: Sequence[Bucket]) -> float | None:
    if len(buckets) < 2:
        return None
    means = [bucket.mean_outcome for bucket in buckets]
    return max(means) - min(means)


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _circular_shift(values: Sequence[float] | Sequence[int], offset: int) -> list[float] | list[int]:
    return [values[(index - offset) % len(values)] for index in range(len(values))]


def _rebuild_iid_price_path(
    first_close: float, log_returns: Sequence[float], rng: random.Random
) -> list[float]:
    rebuilt = [first_close]
    for _ in log_returns:
        rebuilt.append(rebuilt[-1] * math.exp(log_returns[rng.randrange(len(log_returns))]))
    return rebuilt


def _finish_null(
    observed_spread: float, null_spreads: Sequence[float], *, discarded_draws: int
) -> NullResult:
    if not null_spreads:
        return NullResult(observed_spread, None, False, (), discarded_draws)
    threshold = _percentile(null_spreads, 0.975)
    return NullResult(
        observed_spread,
        threshold,
        observed_spread > threshold,
        tuple(null_spreads),
        discarded_draws,
    )


def _empty_null(observed_spread: float | None) -> NullResult:
    return NullResult(observed_spread, None, False, ())


def _normalize_segments(length: int, segments: Sequence[Segment] | None) -> tuple[Segment, ...]:
    normalized = (Segment(0, length, starts_after_gap=False),) if segments is None else tuple(segments)
    expected_start = 0
    for segment in normalized:
        if segment.start != expected_start or not segment.start < segment.stop <= length:
            raise ValueError("segments must be ordered, non-empty, and cover all retained bars")
        expected_start = segment.stop
    if expected_start != length:
        raise ValueError("segments must cover all retained bars")
    return normalized


def _null_rng(name: str) -> random.Random:
    return random.Random(f"{FROZEN.seed}:{name}")


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = math.ceil((len(ordered) - 1) * probability)
    return ordered[position]
