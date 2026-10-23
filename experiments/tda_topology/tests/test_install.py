"""The install spike: the PH backend and the main package must both import,
and the backend must find the topology of a shape we already know."""
import math

import numpy as np


def _circle(n=40, radius=1.0):
    return np.array([[radius * math.cos(2 * math.pi * i / n),
                      radius * math.sin(2 * math.pi * i / n)]
                     for i in range(n)])


def test_main_package_imports():
    from moonface.research.microscope.events import POWER_FLOOR
    assert POWER_FLOOR == 30


def test_backend_finds_one_loop_in_a_circle():
    from ripser import ripser
    dgms = ripser(_circle(), maxdim=1)["dgms"]
    h1 = [(b, d) for b, d in dgms[1] if np.isfinite(d)]
    long_lived = [(b, d) for b, d in h1 if d - b > 0.5]
    assert len(long_lived) == 1
