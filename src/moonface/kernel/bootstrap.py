"""The six bootstrap-resampling shapes found duplicated across kernel/,
research/, signal/, and tools/ (14 call sites total, per the audit in this
phase's plan). Each function here reproduces one site's exact PRNG-consumption
sequence -- these are NOT interchangeable modes of one generic resampler;
random.choices and a manual randrange loop consume Python's Mersenne Twister
stream differently for the same seed, so forcing a false equivalence between
them would silently change every historical bootstrap number computed under
the old code. Migrating a call site means picking the ONE function here that
matches its current shape."""
from __future__ import annotations

import random


def iid_resample_randrange(rng: random.Random, data: list) -> list:
    """n draws of data[rng.randrange(n)] -- the manual with-replacement loop
    used by kernel.power_harness._resample_mean_iid, research.microscope.
    events.bootstrap_ci, tools.promote.mc_drawdown_p95, research.sizing.
    monte_carlo_drawdown, and (via data=list(range(n)), reproducing
    [rng.randrange(n) for _ in range(n)] exactly) research.advval.
    retrodiction's inline index-resample."""
    n = len(data)
    return [data[rng.randrange(n)] for _ in range(n)]


def iid_resample_choices(rng: random.Random, data: list) -> list:
    """rng.choices(data, k=len(data)) -- used by research.macro_event.
    bootstrap_p_le0. Consumes the PRNG stream differently from
    iid_resample_randrange for the same seed; do not substitute one for the
    other on an existing call site."""
    return rng.choices(data, k=len(data))


def circular_block_resample(rng: random.Random, data: list, block_len: int) -> list:
    """Blocks starting anywhere in [0, n) and wrapping via modulo when a
    block runs past the end; stops mid-block once the output reaches length
    n. Used by kernel.power_harness._resample_mean_block."""
    n = len(data)
    out: list = []
    while len(out) < n:
        start = rng.randrange(n)
        for offset in range(block_len):
            out.append(data[(start + offset) % n])
            if len(out) == n:
                break
    return out


def moving_block_resample(rng: random.Random, data: list, block_len: int,
                          target_len: int | None = None) -> list:
    """Blocks starting in [0, n-block_len+1) (never wrapping, never running
    past the end), extended until length >= target_len, then truncated to
    target_len. target_len defaults to len(data) -- the shape used by
    research.carry_measure.block_bootstrap_dd's inline loop and
    research.fwd_analysis.moving_block_resample (both resample to their own
    input's length). research.fwd_analysis.ruin_probability resamples to an
    explicit horizon_trades length instead, which is why target_len is a
    parameter here rather than hardcoded to len(data) -- passing it
    explicitly as len(data) reproduces the two original callers' behavior
    exactly, and passing horizon_trades reproduces ruin_probability's.

    The max(1, ...) floor is a no-op whenever n > block_len (every current
    caller's precondition) and only matters for degenerate n <= block_len
    inputs, which fwd_analysis.moving_block_resample already had to guard."""
    n = len(data)
    limit = n if target_len is None else target_len
    out: list = []
    while len(out) < limit:
        start = rng.randrange(0, max(1, n - block_len + 1))
        out.extend(data[start:start + block_len])
    return out[:limit]


def fixed_block_count_resample(rng: random.Random, data: list, block_len: int,
                               n_blocks: int) -> list:
    """Exactly n_blocks blocks, each starting in [0, len(data)-block_len]
    (inclusive, via randint), concatenated -- not truncated or padded to any
    particular length. Used by research.vrp_measure.block_bootstrap_mean_ci."""
    max_start = len(data) - block_len
    out: list = []
    for _ in range(n_blocks):
        start = rng.randint(0, max_start)
        out.extend(data[start:start + block_len])
    return out


def resample_by_block_key(rng: random.Random, blocks: dict, keys: list) -> list:
    """len(keys) redraws of a whole block, chosen by re-indexing into keys
    each time (so the same block can appear more than once, and the output
    length is whatever the sum of the drawn blocks' lengths happens to be --
    not fixed to len(data)). Used by signal.engine.calibration.
    block_bootstrap_rho_ci, signal.engine.audit.block_ci, and signal.engine.
    repair.block_ci_q (the latter two independently reimplement this exact
    shape, generalized with key_fn/stat_fn parameters -- confirmed by the
    audit in this phase's plan)."""
    out: list = []
    for _ in range(len(keys)):
        out.extend(blocks[keys[rng.randrange(len(keys))]])
    return out


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]. The one formula behind
    research.carry_measure.percentile and research.vrp_measure.percentile,
    confirmed identical before this consolidation."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (q / 100.0) * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac
