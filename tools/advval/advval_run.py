#!/usr/bin/env python
"""advval one-touch run: compute the four cell AUCs + retrodiction verdict.

Real data loaders are the default; tests inject synthetic loaders. All runtime
parameters come from the frozen registration JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.advval.features import (  # noqa: E402
    build_dataset,
    funding_features,
    oi_features,
    price_features,
)
from moonface.research.advval.gbt import cv_auc  # noqa: E402
from moonface.research.advval.retrodiction import retrodiction_verdict  # noqa: E402


def default_loaders(cfg: dict, cache_dir: str) -> dict:
    from moonface.data.series import (  # noqa: E402
        FundingCache,
        align_metric,
        fetch_funding_history,
        fetch_metrics_history,
    )
    from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

    def candles(interval: str):
        return fetch_perp_candles(
            cfg["symbol"],
            interval,
            cfg["window_start_ms"],
            cfg["window_end_ms"],
            cache_dir,
        )

    def funding():
        return fetch_funding_history(
            cfg["exchange"],
            cfg["funding_symbol"],
            cfg["window_start_ms"],
            cfg["window_end_ms"],
            cache=FundingCache(cache_dir),
        )

    def oi(candles_4h):
        rows = fetch_metrics_history(
            cfg["symbol"],
            cfg["window_start_ms"],
            cfg["window_end_ms"],
            cache_dir,
        )
        points = [
            (ts, fields[cfg["metrics_field"]])
            for ts, fields in rows
            if cfg["metrics_field"] in fields
        ]
        return align_metric(candles_4h, points)

    return {"candles": candles, "funding": funding, "oi": oi}


def compute_cell_aucs(cfg: dict, loaders: dict) -> dict[str, dict]:
    gbt = cfg["gbt"]
    cv = cfg["cv"]
    split = cfg["era_split_ms"]

    def score(feats: dict[str, list[float | None]], timestamps: list[int]) -> dict:
        X, y, _ = build_dataset(feats, timestamps, split)
        n_era1 = sum(y)
        auc = cv_auc(
            X,
            y,
            n_folds=cv["n_folds"],
            embargo=cv["embargo"],
            rounds=gbt["rounds"],
            lr=gbt["lr"],
            min_leaf=gbt["min_leaf"],
        )
        return {
            "auc": auc,
            "n_rows": len(y),
            "n_era0": len(y) - n_era1,
            "n_era1": n_era1,
        }

    c4 = loaders["candles"]("4h")
    c1 = loaders["candles"]("1d")
    funding_pts = loaders["funding"]()

    return {
        "price_4h": score(price_features(c4), [c.timestamp_ms for c in c4]),
        "price_1d": score(price_features(c1), [c.timestamp_ms for c in c1]),
        "funding_8h": score(
            funding_features(funding_pts), [ts for ts, _ in funding_pts]
        ),
        "oi_4h": score(oi_features(loaders["oi"](c4)), [c.timestamp_ms for c in c4]),
    }


def _result_md(cfg: dict, cells: dict, retro: dict) -> str:
    lines = [
        "# advval RESULT",
        "",
        f"- registered window end: {cfg['window_end_ms']}",
        f"- era split: {cfg['era_split_ms']} (2024-01-10T00:00:00Z)",
        "",
        "| cell | AUC | rows | era0 | era1 |",
        "|---|---|---|---|---|",
    ]
    for name in cfg["cells"]:
        cell = cells[name]
        lines.append(
            f"| {name} | {cell['auc']:.4f} | {cell['n_rows']} | {cell['n_era0']} | {cell['n_era1']} |"
        )
    lines += [
        "",
        "## Retrodiction",
        "",
        f"- rho: {retro['rho']}",
        f"- 90% CI: [{retro['ci_low']}, {retro['ci_high']}]",
        f"- n_studies: {retro['n_studies']}",
        f"- **VERDICT: {retro['verdict'].upper()}**"
        + (f" ({retro['reason']})" if retro.get("reason") else ""),
    ]
    return "\n".join(lines) + "\n"


def cmd_run(
    out_dir: Path, cache_dir: str, loaders: dict | None = None
) -> dict:
    reg_path = out_dir / "registration.json"
    if not reg_path.exists():
        sys.exit(f"{reg_path} missing; run --register first (and commit it)")
    results_path = out_dir / "results.json"
    if results_path.exists():
        sys.exit(f"{results_path} already exists; the run is one-touch")

    cfg = json.loads(reg_path.read_text())
    if loaders is None:
        loaders = default_loaders(cfg, cache_dir)

    cells = compute_cell_aucs(cfg, loaders)
    retro = retrodiction_verdict(
        {name: cells[name]["auc"] for name in cfg["cells"]},
        n_boot=cfg["bootstrap"]["n_boot"],
        seed=cfg["bootstrap"]["seed"],
    )
    result = {"cells": cells, "retrodiction": retro}
    # Write the human-readable report first; `results.json` is the one-touch marker.
    (out_dir / "RESULT.md").write_text(_result_md(cfg, cells, retro))
    results_path.write_text(json.dumps(result, indent=2))
    print(
        f"verdict: {retro['verdict']} (rho={retro['rho']}, "
        f"ci=[{retro['ci_low']}, {retro['ci_high']}])"
    )
    return result
