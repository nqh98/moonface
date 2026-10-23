"""C3 monotone calibration: isotonic regression of net R on score."""
from moonface.models.engine.repair import apply_isotonic, fit_isotonic

from tests.helpers_repair import ht


def test_fit_is_monotone_and_pools_violations():
    train = ([ht(i, 40, -0.2) for i in range(0, 300, 10)]
             + [ht(i, 60, 0.3) for i in range(300, 600, 10)]
             + [ht(i, 80, 0.1) for i in range(600, 900, 10)])
    curve = fit_isotonic(train)
    assert [s for s, _ in curve] == [40, 60, 80]
    vals = [v for _, v in curve]
    assert vals == sorted(vals)
    assert abs(vals[0] - (-0.2)) < 1e-9
    # 60 (0.3, n=30) and 80 (0.1, n=30) violate -> pooled to 0.2
    assert abs(vals[1] - 0.2) < 1e-9 and abs(vals[2] - 0.2) < 1e-9


def test_apply_is_a_right_continuous_step_lookup():
    curve = ((40, -0.2), (60, 0.2), (80, 0.2))
    assert apply_isotonic(30, curve) == -0.2
    assert apply_isotonic(40, curve) == -0.2
    assert apply_isotonic(59, curve) == -0.2
    assert apply_isotonic(60, curve) == 0.2
    assert apply_isotonic(95, curve) == 0.2


def test_empty_inputs():
    assert fit_isotonic([]) == ()
    assert apply_isotonic(70, ()) == 0.0
