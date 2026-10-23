"""Descriptive go/no-go probe for the macro-liquidity regime instrument.

IN-SAMPLE, DESCRIPTIVE ONLY. No gate, no DSR, no lockbox, no trading, no edge claim.
It answers exactly one question cheaply: do BTC forward outcomes (return / realized vol)
*separate* across the GMM regimes at all? If they do not separate even in-sample, the
"macro regime as a BTC filter" idea is dead without spending any sealed data. If they do,
that only licenses writing a *pre-registered* filter study (which reopens a closed axis and
needs explicit authorization).

Consumes the labeled frame produced by ``macro_regime_model.build_regime_frame``.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import macro_regime_model as mrm

DEFAULT_HORIZONS = (1, 5, 20)


def add_forward_outcomes(frame: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """Append forward BTC log-return and forward realized vol at each horizon.

    fwd_logret_h at t = log(BTC_close[t+h] / BTC_close[t]).
    fwd_vol_h    at t = std of daily BTC_logret over (t, t+h]  (trailing rolling std shifted
    back by h). Rows without a full forward window become NaN and are excluded per-column.
    """
    out = frame.copy()
    logc = np.log(out["BTC_close"])
    daily = out["BTC_logret"]
    for h in horizons:
        out[f"fwd_logret_{h}"] = logc.shift(-h) - logc
        out[f"fwd_vol_{h}"] = daily.rolling(h).std().shift(-h)
    return out


def regime_outcome_table(frame: pd.DataFrame, n_components: int,
                         horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """One row per regime state: n, occupancy, and mean forward return/vol per horizon."""
    enriched = add_forward_outcomes(frame, horizons)
    rows = []
    for k in range(n_components):
        sub = enriched[enriched["regime_argmax"] == k]
        row = {"state": k, "n": int(len(sub)),
               "occupancy": float(len(sub) / len(enriched)) if len(enriched) else float("nan")}
        for h in horizons:
            row[f"mean_fwd_logret_{h}"] = float(sub[f"fwd_logret_{h}"].mean())
            row[f"mean_fwd_vol_{h}"] = float(sub[f"fwd_vol_{h}"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def separation_summary(table: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """Descriptive eyeball metric: spread of mean forward return across states per horizon.

    spread_h = max_state(mean_fwd_logret_h) - min_state(mean_fwd_logret_h). Bigger spread =
    the regimes carve BTC forward returns more. This is a description, NOT a significance test.
    """
    rows = []
    for h in horizons:
        col = table[f"mean_fwd_logret_{h}"]
        rows.append({"horizon": h, "return_spread": float(col.max() - col.min()),
                     "vol_spread": float(table[f"mean_fwd_vol_{h}"].max()
                                         - table[f"mean_fwd_vol_{h}"].min())})
    return pd.DataFrame(rows)


def entropy_split_table(frame: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """Do confident (low-entropy) days behave differently from uncertain (high-entropy) days?

    Split on the median of entropy_norm; report mean forward return/vol per bucket per horizon.
    """
    enriched = add_forward_outcomes(frame, horizons)
    median = enriched["entropy_norm"].median()
    buckets = {"low_entropy": enriched[enriched["entropy_norm"] <= median],
               "high_entropy": enriched[enriched["entropy_norm"] > median]}
    rows = []
    for name, sub in buckets.items():
        row = {"bucket": name, "n": int(len(sub))}
        for h in horizons:
            row[f"mean_fwd_logret_{h}"] = float(sub[f"fwd_logret_{h}"].mean())
            row[f"mean_fwd_vol_{h}"] = float(sub[f"fwd_vol_{h}"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


# Boundaries splitting the labeled series into distinct macro eras.
# Note: walk-forward labels begin ~2 years after --start (warmup), so the first era is
# effectively the tail of its range (e.g. 2018-2019 for a 2016 start).
DEFAULT_ERA_BOUNDS = ("2020-01-01", "2023-01-01")


def era_split(frame: pd.DataFrame, bounds=DEFAULT_ERA_BOUNDS) -> "dict[str, pd.DataFrame]":
    """Partition a labeled frame into consecutive date eras (disjoint, exhaustive)."""
    edges = [pd.Timestamp(b) for b in bounds]
    idx = frame.index
    eras: dict[str, pd.DataFrame] = {}
    eras[f"..{bounds[0][:4]}"] = frame[idx < edges[0]]
    for i in range(len(edges) - 1):
        eras[f"{bounds[i][:4]}..{bounds[i + 1][:4]}"] = frame[(idx >= edges[i]) & (idx < edges[i + 1])]
    eras[f"{bounds[-1][:4]}.."] = frame[idx >= edges[-1]]
    return eras


def era_stability_report(frame: pd.DataFrame, n_components: int, horizon: int = 20,
                         bounds=DEFAULT_ERA_BOUNDS) -> pd.DataFrame:
    """Per-era check of the two candidate patterns at ``horizon``:

    - ``state1_is_flattest``: is regime State 1 the lowest mean forward return of all states?
      (State identity is canonical across refits: ascending DXY-return component mean.)
    - ``entropy_monotone``: do low-entropy (confident) days beat high-entropy (uncertain) days?

    ``pattern_holds`` is the conjunction. If it is not True in *every* era, the macro-exogenous
    hypothesis is FRAGILE.
    """
    col = f"mean_fwd_logret_{horizon}"
    rows = []
    for name, sub in era_split(frame, bounds).items():
        if len(sub) < horizon + n_components + 5:
            rows.append({"era": name, "n": int(len(sub)), "state1_is_flattest": None,
                         "entropy_monotone": None, "pattern_holds": None, "note": "too_small"})
            continue
        table = regime_outcome_table(sub, n_components, horizons=(horizon,))
        state1 = float(table.loc[table["state"] == 1, col].iloc[0])
        argmin_state = int(table.loc[table[col].idxmin(), "state"])
        spread = float(table[col].max() - table[col].min())
        esplit = entropy_split_table(sub, horizons=(horizon,))
        lo = float(esplit.loc[esplit["bucket"] == "low_entropy", col].iloc[0])
        hi = float(esplit.loc[esplit["bucket"] == "high_entropy", col].iloc[0])
        flat = argmin_state == 1
        monotone = lo > hi
        rows.append({
            "era": name, "n": int(len(sub)),
            f"state1_fwd{horizon}": state1, "argmin_state": argmin_state,
            "state1_is_flattest": flat, "return_spread": spread,
            f"low_ent_fwd{horizon}": lo, f"high_ent_fwd{horizon}": hi,
            "entropy_monotone": monotone, "pattern_holds": bool(flat and monotone),
        })
    return pd.DataFrame(rows)


def era_verdict(report: pd.DataFrame) -> str:
    """FRAGILE unless ``pattern_holds`` is True in every sized era."""
    sized = report[report["pattern_holds"].notna()]
    if len(sized) == 0:
        return "INCONCLUSIVE (no era large enough)"
    if bool(sized["pattern_holds"].all()):
        return "STABLE across all eras (licenses a pre-registered study; still needs authorization)"
    return "FRAGILE/DEAD — pattern does not hold in every era; close the lane, spend no sealed data"


def _fmt(df: pd.DataFrame) -> str:
    return df.to_string(index=False, float_format=lambda x: f"{x:.5f}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Descriptive regime/BTC-outcome go-no-go probe.")
    p.add_argument("--start", required=True)
    p.add_argument("--end", default=None)
    p.add_argument("--components", type=int, default=3)
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--mode", choices=["split", "walkforward"], default="walkforward")
    p.add_argument("--warmup", type=int, default=504)
    p.add_argument("--step", type=int, default=63)
    p.add_argument("--cache-dir", default="data")
    p.add_argument("--horizons", default="1,5,20")
    p.add_argument("--era-check", action="store_true",
                   help="also run the per-era stability probe at --era-horizon")
    p.add_argument("--era-horizon", type=int, default=20)
    args = p.parse_args(argv)
    horizons = tuple(int(h) for h in args.horizons.split(","))

    frame = mrm.build_regime_frame(
        start=args.start, end=args.end, n_components=args.components, window=args.window,
        mode=args.mode, warmup=args.warmup, step=args.step, cache_dir=args.cache_dir,
        fetcher=mrm._yf_fetch,
    )
    table = regime_outcome_table(frame, args.components, horizons)

    print("=== IN-SAMPLE DESCRIPTIVE PROBE (no gate, no edge claim) ===")
    print(f"labeled rows: {len(frame)}  horizons: {horizons}\n")
    print("Per-regime forward BTC outcomes:")
    print(_fmt(table))
    print("\nRegime separation (descriptive spread across states):")
    print(_fmt(separation_summary(table, horizons)))
    print("\nEntropy split (confident vs uncertain days):")
    print(_fmt(entropy_split_table(frame, horizons)))

    if args.era_check:
        report = era_stability_report(frame, args.components, horizon=args.era_horizon)
        print(f"\n=== ERA-STABILITY PROBE (h={args.era_horizon}, in-sample, no gate) ===")
        print(_fmt(report))
        print(f"\nVERDICT: {era_verdict(report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
