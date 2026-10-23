"""Back-compat shim: the SMC detectors now live in moonface.core.smc.

Kept so every existing import path (tests, smc_variants, leaderboards) stays
byte-identical after the detector promotion to foundation."""
from moonface.core.smc import *  # noqa: F401,F403
