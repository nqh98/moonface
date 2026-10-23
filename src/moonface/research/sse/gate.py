from __future__ import annotations

import random
from dataclasses import dataclass

from moonface.core.models import Candle

from moonface.research.sse.episodes import entry_episodes

POWER_FLOOR = 30


@dataclass(frozen=True)
class NullResult:
    observed: float
    threshold: float
    pass_: bool


def powered_bucket_means(episodes: list[dict], *, power_floor: int = POWER_FLOOR) -> dict[int, dict]:
    buckets: dict[int, list[float]] = {}
    for row in episodes:
        buckets.setdefault(int(row["cluster"]), []).append(float(row["fwd_r"]))
    out: dict[int, dict] = {}
    for cluster, vals in buckets.items():
        if len(vals) >= power_floor:
            out[cluster] = {"n": len(vals), "mean": sum(vals) / len(vals)}
    return out


def spread_stat(episodes: list[dict], *, power_floor: int = POWER_FLOOR) -> float:
    buckets = powered_bucket_means(episodes, power_floor=power_floor)
    means = [bucket["mean"] for bucket in buckets.values()]
    if len(means) < 2:
        return 0.0
    return max(means) - min(means)


def label_shuffle_null(
    episodes: list[dict],
    *,
    draws: int = 1000,
    seed: int = 1,
    power_floor: int = POWER_FLOOR,
    quantile: float = 0.975,
) -> NullResult:
    observed = spread_stat(episodes, power_floor=power_floor)
    rng = random.Random(seed)
    labels = [row["cluster"] for row in episodes]
    stats: list[float] = []
    for _ in range(draws):
        shuffled = list(labels)
        rng.shuffle(shuffled)
        fake = [{**row, "cluster": shuffled[i]} for i, row in enumerate(episodes)]
        stats.append(spread_stat(fake, power_floor=power_floor))
    ordered = sorted(stats)
    threshold = ordered[min(len(ordered) - 1, int(quantile * len(ordered)))] if ordered else 0.0
    return NullResult(observed=observed, threshold=threshold, pass_=observed > threshold)


def circular_shift_null(
    labels: list[int],
    candles: list[Candle],
    *,
    horizon: int = 24,
    draws: int = 1000,
    seed: int = 1,
    power_floor: int = POWER_FLOOR,
    quantile: float = 0.975,
) -> NullResult:
    observed = spread_stat(entry_episodes(labels, candles, horizon=horizon), power_floor=power_floor)
    if len(labels) <= horizon + 1:
        return NullResult(observed=observed, threshold=0.0, pass_=False)
    rng = random.Random(seed)
    valid = [shift for shift in range(horizon, len(labels)) if shift < len(labels)]
    stats: list[float] = []
    for _ in range(draws):
        shift = rng.choice(valid)
        rotated = labels[shift:] + labels[:shift]
        stats.append(
            spread_stat(entry_episodes(rotated, candles, horizon=horizon), power_floor=power_floor)
        )
    ordered = sorted(stats)
    threshold = ordered[min(len(ordered) - 1, int(quantile * len(ordered)))] if ordered else 0.0
    return NullResult(observed=observed, threshold=threshold, pass_=observed > threshold)


def circular_shift_episode_null(
    episodes: list[dict],
    *,
    draws: int = 1000,
    seed: int = 1,
    power_floor: int = POWER_FLOOR,
    quantile: float = 0.975,
) -> NullResult:
    observed = spread_stat(episodes, power_floor=power_floor)
    if len(episodes) < 3:
        return NullResult(observed=observed, threshold=0.0, pass_=False)
    rng = random.Random(seed)
    labels = [row["cluster"] for row in episodes]
    valid = list(range(1, len(labels)))
    stats: list[float] = []
    for _ in range(draws):
        shift = rng.choice(valid)
        rotated = labels[shift:] + labels[:shift]
        fake = [{**row, "cluster": rotated[i]} for i, row in enumerate(episodes)]
        stats.append(spread_stat(fake, power_floor=power_floor))
    ordered = sorted(stats)
    threshold = ordered[min(len(ordered) - 1, int(quantile * len(ordered)))] if ordered else 0.0
    return NullResult(observed=observed, threshold=threshold, pass_=observed > threshold)


def era_stability(
    episodes: list[dict],
    *,
    power_floor: int = POWER_FLOOR,
) -> dict:
    by_era: dict[int, list[dict]] = {}
    for row in episodes:
        era = row.get("era")
        if era is not None:
            by_era.setdefault(int(era), []).append(row)
    era1 = powered_bucket_means(by_era.get(1, []), power_floor=power_floor)
    if len(era1) < 2:
        return {"pass": False, "reason": "era1_underpowered"}
    ordered = sorted(era1.items(), key=lambda item: item[1]["mean"])
    bottom, top = ordered[0][0], ordered[-1][0]
    target_sign = era1[top]["mean"] - era1[bottom]["mean"]
    if target_sign == 0.0:
        return {"pass": False, "reason": "flat_era1"}
    for era in (2, 3):
        buckets = powered_bucket_means(by_era.get(era, []), power_floor=power_floor)
        if top not in buckets or bottom not in buckets:
            return {"pass": False, "reason": f"era{era}_underpowered", "top": top, "bottom": bottom}
        spread = buckets[top]["mean"] - buckets[bottom]["mean"]
        if spread == 0.0 or spread * target_sign <= 0.0:
            return {"pass": False, "reason": f"era{era}_sign_flip", "top": top, "bottom": bottom}
    return {"pass": True, "top": top, "bottom": bottom}


def gate0_result(
    *,
    track_n_episodes: list[dict],
    track_l_episodes: list[dict],
    labels: list[int],
    candles: list[Candle],
    horizon: int = 24,
    draws: int = 1000,
    seed: int = 1,
    power_floor: int = POWER_FLOOR,
) -> dict:
    label_null = label_shuffle_null(
        track_n_episodes, draws=draws, seed=seed, power_floor=power_floor
    )
    circular_null = circular_shift_episode_null(
        track_n_episodes, draws=draws, seed=seed + 1, power_floor=power_floor
    )
    n_spread = spread_stat(track_n_episodes, power_floor=power_floor)
    l_spread = spread_stat(track_l_episodes, power_floor=power_floor)
    stability = era_stability(track_n_episodes, power_floor=power_floor)
    control_label = label_shuffle_null(
        track_l_episodes, draws=draws, seed=seed + 2, power_floor=power_floor
    )
    control_circ = circular_shift_episode_null(
        track_l_episodes,
        draws=draws,
        seed=seed + 3,
        power_floor=power_floor,
    )
    suspect = control_label.pass_ or control_circ.pass_
    verdict = "PASS" if (
        label_null.pass_
        and circular_null.pass_
        and n_spread > l_spread
        and stability["pass"]
        and not suspect
    ) else "FAIL"
    if suspect:
        verdict = "SUSPECT_HARNESS"
    return {
        "verdict": verdict,
        "track_n_spread": n_spread,
        "track_l_spread": l_spread,
        "label_shuffle": {
            "observed": label_null.observed,
            "threshold": label_null.threshold,
            "pass": label_null.pass_,
        },
        "circular_shift": {
            "observed": circular_null.observed,
            "threshold": circular_null.threshold,
            "pass": circular_null.pass_,
        },
        "attribution_pass": n_spread > l_spread,
        "era_stability": stability,
        "control_nulls": {
            "label_shuffle_pass": control_label.pass_,
            "circular_shift_pass": control_circ.pass_,
        },
    }
