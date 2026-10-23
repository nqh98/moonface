import dataclasses
import math

from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.normalize import Normalizer


def test_rank_is_signed_and_bounded():
    cfg = MoeConfig()
    norm = Normalizer.fit({"E": [0.1, 0.2, 0.3, 0.4]}, cfg)
    assert norm.transform("E", 0.0) == 0.0
    top = norm.transform("E", 0.4)
    bot = norm.transform("E", 0.05)
    assert 0.0 < bot < top <= 1.0
    assert norm.transform("E", -0.4) == -top


def test_unknown_expert_is_zero():
    norm = Normalizer.fit({"E": [0.1, 0.2]}, MoeConfig())
    assert norm.transform("UNKNOWN", 0.9) == 0.0


def test_tanh_mode_monotone_and_bounded():
    cfg = dataclasses.replace(MoeConfig(), norm_mode="tanh")
    norm = Normalizer.fit({"E": [0.1, 0.2, 0.3, 0.4, 0.5]}, cfg)
    lo = norm.transform("E", 0.1)
    hi = norm.transform("E", 0.5)
    assert -1.0 < lo < hi < 1.0
    assert math.isclose(norm.transform("E", 0.0), 0.0, abs_tol=0.5)
