"""Makes the lane's top-level modules (grid, tda_features, ...) importable
without a package __init__.py -- same fix as experiments/macro_regime/,
centralized here instead of repeated per test file."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
