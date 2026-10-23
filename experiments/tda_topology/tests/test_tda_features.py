import math
import random

from tda_features import (FEATURE_KEYS, W, build_features, corr_distance,
                          landscape_norms, persistence_diagrams,
                          persistence_entropy, spearman_corr,
                          total_persistence, wasserstein1)


def test_spearman_is_monotone_invariant():
    # Spearman sees rank, so a monotone transform must not move it.
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [1.0, 4.0, 9.0, 16.0, 25.0]
    rho = spearman_corr([a, b])
    assert rho[0][1] == 1.0


def test_corr_distance_maps_perfect_correlation_to_zero():
    d = corr_distance([[1.0, 1.0], [1.0, 1.0]])
    assert d[0][1] == 0.0


def test_corr_distance_maps_perfect_anticorrelation_to_two():
    d = corr_distance([[1.0, -1.0], [-1.0, 1.0]])
    assert d[0][1] == 2.0


def test_two_separated_clusters_give_two_h0_classes():
    # Points at distance 0 within a cluster, 10 across: exactly two
    # components survive until the clusters merge.
    n = 6
    dist = [[0.0 if (i < 3) == (j < 3) else 10.0 for j in range(n)]
            for i in range(n)]
    h0, _ = persistence_diagrams(dist)
    long_lived = [(b, d) for b, d in h0 if d - b > 1.0]
    assert len(long_lived) == 1   # the infinite class is dropped; one finite
    assert long_lived[0][1] == 10.0


def test_circle_gives_exactly_one_persistent_loop():
    n = 40
    pts = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
           for i in range(n)]
    dist = [[math.dist(p, q) for q in pts] for p in pts]
    _, h1 = persistence_diagrams(dist)
    long_lived = [(b, d) for b, d in h1 if d - b > 0.5]
    assert len(long_lived) == 1


def test_persistence_entropy_is_zero_for_one_bar_and_none_for_empty():
    assert persistence_entropy([(0.0, 1.0)]) == 0.0
    assert persistence_entropy([]) is None


def test_persistence_entropy_is_maximal_for_equal_bars():
    two_equal = persistence_entropy([(0.0, 1.0), (0.0, 1.0)])
    lopsided = persistence_entropy([(0.0, 1.0), (0.0, 0.01)])
    assert two_equal == math.log(2)
    assert lopsided < two_equal


def test_total_persistence_sums_lifetimes():
    assert total_persistence([(0.0, 1.0), (2.0, 4.5)]) == 3.5


def test_landscape_norms_scale_with_the_bar():
    small_l1, small_l2 = landscape_norms([(0.0, 1.0)])
    big_l1, big_l2 = landscape_norms([(0.0, 2.0)])
    assert big_l1 > small_l1 > 0.0
    assert big_l2 > small_l2 > 0.0
    assert landscape_norms([]) == (0.0, 0.0)


def test_wasserstein_is_zero_for_identical_diagrams():
    dgm = [(0.0, 1.0), (0.5, 2.0)]
    assert wasserstein1(dgm, dgm) == 0.0


def test_wasserstein_matches_a_point_to_the_diagonal_when_unpaired():
    # A single bar of lifetime 1.0 against an empty diagram costs its
    # diagonal projection, 0.5.
    assert wasserstein1([(0.0, 1.0)], []) == 0.5


def test_wasserstein_grows_with_a_shifted_point():
    assert wasserstein1([(0.0, 1.0)], [(0.0, 1.0)]) == 0.0
    assert wasserstein1([(0.0, 1.0)], [(0.0, 1.4)]) > 0.0


def _synthetic_returns(n_assets, n_bars, seed=0):
    rng = random.Random(seed)
    return {f"A{i}": [rng.gauss(0.0, 0.01) for _ in range(n_bars)]
            for i in range(n_assets)}


def test_below_cross_section_floor_emits_no_features():
    rets = _synthetic_returns(7, W + 5)          # 7 < XS_MIN_ASSETS = 8
    feats = build_features(rets, n_bars=W + 5)
    assert all(f["pers_entropy_h0"] is None for f in feats)


def test_at_cross_section_floor_emits_features():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    assert feats[W + 4]["pers_entropy_h0"] is not None


def test_features_before_the_window_is_full_are_none():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    assert all(feats[t]["pers_entropy_h0"] is None for t in range(W - 1))


def test_wasserstein_is_none_when_the_previous_bar_has_no_diagram():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    # The first bar with a full window has no valid t-1, so no comparison.
    first = next(t for t, f in enumerate(feats)
                 if f["pers_entropy_h0"] is not None)
    assert feats[first]["wasserstein_dist"] is None
    assert feats[first + 1]["wasserstein_dist"] is not None


def test_features_are_causal():
    # Truncating the future must not move a past bar's features.
    full = _synthetic_returns(8, W + 40)
    cut = {k: v[:W + 10] for k, v in full.items()}
    f_full = build_features(full, n_bars=W + 40)
    f_cut = build_features(cut, n_bars=W + 10)
    for t in range(W + 10):
        for key in FEATURE_KEYS:
            assert f_full[t][key] == f_cut[t][key]
