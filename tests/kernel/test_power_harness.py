from __future__ import annotations

import math


def _sd(xs: list[float]) -> float:
    mean = sum(xs) / len(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def test_bonferroni_level() -> None:
    from moonface.kernel import power_harness as ph

    assert ph.bonferroni_level(4) == 0.0125
    assert ph.bonferroni_level(1) == 0.05


def test_bonferroni_level_rejects_nonpositive_k() -> None:
    from moonface.kernel import power_harness as ph

    for bad_k in [0, -1]:
        try:
            ph.bonferroni_level(bad_k)
        except ValueError as exc:
            assert "k must be positive" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_bootstrap_all_positive_p_le_zero_zero() -> None:
    from moonface.kernel import power_harness as ph

    means, p = ph.bootstrap_expectancy([1.0, 2.0, 3.0], n_resamples=2000, seed=1)
    assert p == 0.0
    assert means == sorted(means)
    assert len(means) == 2000
    assert min(means) >= 1.0


def test_bootstrap_all_negative_p_le_zero_one() -> None:
    from moonface.kernel import power_harness as ph

    _, p = ph.bootstrap_expectancy([-1.0, -2.0], n_resamples=2000, seed=1)
    assert p == 1.0


def test_bootstrap_empty_input_returns_neutral_result() -> None:
    from moonface.kernel import power_harness as ph

    means, p = ph.bootstrap_expectancy([], n_resamples=10, seed=1)
    assert means == []
    assert p == 1.0


def test_bootstrap_expectancy_rejects_nonpositive_block_len() -> None:
    from moonface.kernel import power_harness as ph

    for bad_block_len in [0, -3]:
        try:
            ph.bootstrap_expectancy([1.0, 2.0], block_len=bad_block_len)
        except ValueError as exc:
            assert "block_len must be positive" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_bootstrap_recovers_mean_center() -> None:
    from moonface.kernel import power_harness as ph

    data = [(-1.0) ** i * 0.5 + 0.2 for i in range(40)]
    means, _ = ph.bootstrap_expectancy(data, n_resamples=5000, seed=7)
    center = means[len(means) // 2]
    assert abs(center - (sum(data) / len(data))) < 0.1


def test_one_sided_lower_picks_percentile() -> None:
    from moonface.kernel import power_harness as ph

    means = [float(i) for i in range(1000)]
    lo = ph.one_sided_lower(means, 0.0125)
    assert lo == 12.0


def test_one_sided_lower_rejects_invalid_alpha() -> None:
    from moonface.kernel import power_harness as ph

    means = [0.0, 1.0, 12.0, 13.0, 250.0, 999.0]
    for bad_alpha in [-0.1, 1.1]:
        try:
            ph.one_sided_lower(means, bad_alpha)
        except ValueError as exc:
            assert "alpha must be between 0 and 1" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_block_bootstrap_runs_and_differs_on_autocorrelated() -> None:
    from moonface.kernel import power_harness as ph

    seq = [1.0] * 20 + [-1.0] * 20
    iid_means, _ = ph.bootstrap_expectancy(seq, n_resamples=3000, seed=3)
    blk_means, _ = ph.bootstrap_expectancy(
        seq,
        n_resamples=3000,
        seed=3,
        block=True,
        block_len=5,
    )
    assert _sd(blk_means) > _sd(iid_means)


def test_pooled_metrics_basic() -> None:
    from moonface.kernel import power_harness as ph

    records = [
        {"net_r": 2.0, "atr_frac": 1.0},
        {"net_r": -1.0, "atr_frac": 1.0},
        {"net_r": 1.0, "atr_frac": 1.0},
    ]
    got = ph.pooled_metrics(records)
    assert got == {
        "trade_count": 3,
        "total_r": 2.0,
        "expectancy_r": 0.6667,
        "profit_factor": 3.0,
        "max_drawdown_r": -1.0,
    }


def test_judge_significant_strong_positive(monkeypatch) -> None:
    from moonface.kernel import power_harness as ph

    records = [{"net_r": 2.0, "atr_frac": 1.0} for _ in range(30)]

    monkeypatch.setattr(
        ph,
        "bootstrap_expectancy",
        lambda net_rs, n_resamples=100_000, seed=20260627, block=False, block_len=1: ([0.4, 0.5, 0.6], 0.0),
    )
    monkeypatch.setattr(ph, "one_sided_lower", lambda means, alpha: 0.4)

    got = ph.judge_signal(
        {"expectancy_r": 0.8},
        {"expectancy_r": 0.7},
        records,
        4,
    )

    assert got["same_sign"] is True
    assert got["practical"] is True
    assert got["cost"] is True
    assert got["significant"] is True
    assert got["verdict"] == "paper_candidate"


def test_judge_significant_uses_bootstrap_p_value_gate(monkeypatch) -> None:
    from moonface.kernel import power_harness as ph

    records = [{"net_r": 2.0, "atr_frac": 1.0} for _ in range(30)]

    monkeypatch.setattr(
        ph,
        "bootstrap_expectancy",
        lambda net_rs, n_resamples=100_000, seed=20260627, block=False, block_len=1: ([-0.4, -0.3, -0.2], 0.0),
    )
    monkeypatch.setattr(ph, "one_sided_lower", lambda means, alpha: -0.4)

    got = ph.judge_signal(
        {"expectancy_r": 0.8},
        {"expectancy_r": 0.7},
        records,
        4,
    )

    assert got["boot_lo"] < 0.0
    assert got["p_le_zero"] < ph.bonferroni_level(4)
    assert got["significant"] is True
    assert got["verdict"] == "paper_candidate"


def test_judge_cost_requires_both_multiples(monkeypatch) -> None:
    from moonface.kernel import power_harness as ph

    records = [{"net_r": 2.0, "atr_frac": 1.0} for _ in range(30)]
    seen: list[float] = []

    monkeypatch.setattr(
        ph,
        "bootstrap_expectancy",
        lambda net_rs, n_resamples=100_000, seed=20260627, block=False, block_len=1: ([0.4, 0.5, 0.6], 0.0),
    )
    monkeypatch.setattr(ph, "one_sided_lower", lambda means, alpha: 0.4)

    def fake_cost_multiple(records_arg, mult: float) -> bool:
        seen.append(mult)
        return mult == 2.0

    monkeypatch.setattr(ph, "cost_multiple", fake_cost_multiple)

    got = ph.judge_signal(
        {"expectancy_r": 0.8},
        {"expectancy_r": 0.7},
        records,
        4,
    )

    assert seen == [2.0, 3.0]
    assert got["cost"] is False
    assert got["verdict"] == "negative"


def test_judge_positive_but_underpowered_is_forward(monkeypatch) -> None:
    from moonface.kernel import power_harness as ph

    records = [{"net_r": 0.01, "atr_frac": 1.0} for _ in range(5)]

    monkeypatch.setattr(
        ph,
        "bootstrap_expectancy",
        lambda net_rs, n_resamples=100_000, seed=20260627, block=False, block_len=1: ([-0.05, 0.01, 0.02], 0.4),
    )
    monkeypatch.setattr(ph, "one_sided_lower", lambda means, alpha: -0.01)

    got = ph.judge_signal(
        {"expectancy_r": 0.01},
        {"expectancy_r": 0.02},
        records,
        4,
    )

    assert got["same_sign"] is True
    assert got["pooled"]["expectancy_r"] > 0
    assert got["significant"] is False
    assert got["verdict"] == "forward_candidate"


def test_judge_sign_flip_is_negative(monkeypatch) -> None:
    from moonface.kernel import power_harness as ph

    records = [{"net_r": 2.0, "atr_frac": 1.0} for _ in range(30)]

    monkeypatch.setattr(
        ph,
        "bootstrap_expectancy",
        lambda net_rs, n_resamples=100_000, seed=20260627, block=False, block_len=1: ([0.4, 0.5, 0.6], 0.0),
    )
    monkeypatch.setattr(ph, "one_sided_lower", lambda means, alpha: 0.4)

    got = ph.judge_signal(
        {"expectancy_r": 0.8},
        {"expectancy_r": -0.2},
        records,
        4,
    )

    assert got["same_sign"] is False
    assert got["verdict"] == "negative"
