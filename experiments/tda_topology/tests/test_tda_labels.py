from moonface.research.microscope.regimes import UNLABELED

from tda_labels import BURN_IN, LABELS, build_labels, expanding_median_flags


def test_flags_are_none_until_burn_in_is_satisfied():
    flags = expanding_median_flags([float(i) for i in range(10)], burn_in=5)
    assert flags[:5] == [None] * 5
    assert flags[5] is not None


def test_flag_compares_against_history_strictly_before_the_bar():
    # History before index 3 is [0, 1, 2], median 1. Value 5 > 1 -> True.
    flags = expanding_median_flags([0.0, 1.0, 2.0, 5.0], burn_in=3)
    assert flags[3] is True


def test_flag_is_causal_appending_the_future_cannot_change_the_past():
    base = [float(i) for i in range(20)]
    short = expanding_median_flags(base, burn_in=5)
    long = expanding_median_flags(base + [999.0] * 20, burn_in=5)
    assert short == long[:20]


def test_none_values_are_skipped_not_counted():
    flags = expanding_median_flags([0.0, None, 1.0, 2.0, 5.0], burn_in=3)
    assert flags[1] is None
    assert flags[4] is True


def test_labels_use_the_four_frozen_names_plus_unlabeled():
    feats = []
    for i in range(BURN_IN + 10):
        feats.append({"pers_entropy_h0": float(i % 7),
                      "wasserstein_dist": float(i % 5)})
    labels = build_labels(feats)
    assert labels[0] == UNLABELED
    assert set(labels[BURN_IN + 1:]) <= set(LABELS)


def test_missing_feature_yields_unlabeled():
    feats = [{"pers_entropy_h0": None, "wasserstein_dist": None}
             for _ in range(BURN_IN + 10)]
    assert build_labels(feats) == [UNLABELED] * (BURN_IN + 10)
