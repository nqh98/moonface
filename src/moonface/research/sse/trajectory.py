from __future__ import annotations

from dataclasses import dataclass

from moonface.research.microscope.features import rolling_z
from moonface.research.sse.axes import AxisMatrix

LOOKBACK = 20
Z_WINDOW = 540
Z_MIN_FRAC = 0.9
FEATURE_NAMES = (
    "breadth_mean",
    "disp_mean",
    "breadth_disp",
    "disp_disp",
    "breadth_path",
    "disp_path",
)


@dataclass(frozen=True)
class TrajectoryMatrix:
    timestamps: list[int]
    rows: list[dict[str, float | None]]


def summarize_trajectories(
    axes: AxisMatrix,
    *,
    lookback: int = LOOKBACK,
    z_window: int = Z_WINDOW,
    min_frac: float = Z_MIN_FRAC,
) -> TrajectoryMatrix:
    raw = {name: [None] * len(axes.timestamps) for name in FEATURE_NAMES}
    bx = axes.breadth_z
    dx = axes.disp_z
    for i in range(lookback - 1, len(axes.timestamps)):
        b_win = bx[i - lookback + 1: i + 1]
        d_win = dx[i - lookback + 1: i + 1]
        if any(v is None for v in b_win) or any(v is None for v in d_win):
            continue
        b_vals = [float(v) for v in b_win]
        d_vals = [float(v) for v in d_win]
        raw["breadth_mean"][i] = sum(b_vals) / lookback
        raw["disp_mean"][i] = sum(d_vals) / lookback
        raw["breadth_disp"][i] = b_vals[-1] - b_vals[0]
        raw["disp_disp"][i] = d_vals[-1] - d_vals[0]
        raw["breadth_path"][i] = sum(abs(b_vals[j] - b_vals[j - 1]) for j in range(1, lookback))
        raw["disp_path"][i] = sum(abs(d_vals[j] - d_vals[j - 1]) for j in range(1, lookback))
    zcols = {
        name: rolling_z(values, window=z_window, min_frac=min_frac)
        for name, values in raw.items()
    }
    rows = [
        {name: zcols[name][i] for name in FEATURE_NAMES}
        for i in range(len(axes.timestamps))
    ]
    return TrajectoryMatrix(timestamps=list(axes.timestamps), rows=rows)

