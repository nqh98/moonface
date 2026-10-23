# tests/test_power_harness_block.py
import random

from moonface.kernel.power_harness import (
    bootstrap_expectancy,
    judge_signal,
    one_sided_lower,
)


def _records(net_rs):
    return [{"net_r": r, "atr_frac": 0.02, "side": "LONG", "i": i}
            for i, r in enumerate(net_rs)]


def _autocorr_net_rs(n=120, seed=1):
    rng = random.Random(seed)
    out, level = [], 0.0
    for _ in range(n):
        level = 0.9 * level + rng.gauss(0.05, 0.3)  # strongly autocorrelated
        out.append(level)
    return out


def test_default_kwargs_match_plain_iid():
    net_rs = _autocorr_net_rs()
    records = _records(net_rs)
    val = {"expectancy_r": 0.2}
    seal = {"expectancy_r": 0.1}
    res = judge_signal(val, seal, records, 3, n_resamples=5000, seed=7)
    means, p = bootstrap_expectancy([r["net_r"] for r in records],
                                    n_resamples=5000, seed=7)
    assert res["p_le_zero"] == p
    assert res["boot_lo"] == one_sided_lower(means, 0.05 / 3)


def test_block_len_one_equals_iid():
    net_rs = _autocorr_net_rs()
    means_iid, p_iid = bootstrap_expectancy(net_rs, n_resamples=5000, seed=7)
    means_blk, p_blk = bootstrap_expectancy(
        net_rs, n_resamples=5000, seed=7, block=True, block_len=1)
    assert (p_iid, means_iid) == (p_blk, means_blk)


def test_block_path_changes_ci_on_autocorrelated_records():
    net_rs = _autocorr_net_rs()
    records = _records(net_rs)
    val = {"expectancy_r": 0.2}
    seal = {"expectancy_r": 0.1}
    iid = judge_signal(val, seal, records, 3, n_resamples=5000, seed=7)
    blk = judge_signal(val, seal, records, 3, n_resamples=5000, seed=7,
                       block=True, block_len=8)
    assert blk["boot_lo"] != iid["boot_lo"]
