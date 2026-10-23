"""State vector: fixed-weight factor compression of the feature matrix.

Nothing is fitted — each factor is the capped equal-weight mean of its
group's available z-scores. Groups and cap are frozen in the design spec."""
from __future__ import annotations

from moonface.research.microscope.features import FeatureMatrix

FACTOR_GROUPS: dict[str, tuple[str, ...]] = {
    "trend": ("ret_1_z", "ret_6_z", "ret_42_z", "dist_ma_z", "persist_z"),
    "vol": ("rvol_z", "atr_z", "range_z"),
    "crowding": ("funding_z", "oi_chg_z"),
    "flow": ("volume_z",),
    "relative_strength": ("rs_xz",),
}
# resid_z and beta_btc (FEATURE_KEYS) are intentionally descriptive-only and
# never enter a factor group.
FACTOR_NAMES = tuple(FACTOR_GROUPS)
FACTOR_CAP = 3.0


def state_row(features: dict[str, float | None]) -> dict[str, float | None]:
    """One state vector from one feature row: capped mean of available
    group members, None when the whole group is missing."""
    out: dict[str, float | None] = {}
    for name, keys in FACTOR_GROUPS.items():
        vals = [features[k] for k in keys if features.get(k) is not None]
        if not vals:
            out[name] = None
        else:
            m = sum(vals) / len(vals)
            out[name] = max(-FACTOR_CAP, min(FACTOR_CAP, m))
    return out


def state_vectors(
        matrix: FeatureMatrix) -> dict[str, list[dict[str, float | None]]]:
    return {sym: [state_row(r) for r in rows]
            for sym, rows in matrix.rows.items()}
