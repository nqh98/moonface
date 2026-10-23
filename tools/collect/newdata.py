#!/usr/bin/env python
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.newdata import (
    DATA_CLASSES,
    assess_manifest,
    load_manifest,
    render_candidates,
    render_report,
)


def cmd_candidates(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "candidates.json").write_text(render_candidates())


def cmd_register(out_dir: Path, provider: str, data_class: str) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the new-data readiness design is frozen")
    if data_class not in DATA_CLASSES:
        sys.exit(f"data_class must be one of: {', '.join(DATA_CLASSES)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    reg = {
        "registered_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provider": provider,
        "data_class": data_class,
        "purpose": "data readiness only",
        "forbidden_actions": [
            "signal tests",
            "return tests",
            "strategy backtests",
            "parameter search",
        ],
    }
    path.write_text(json.dumps(reg, indent=2) + "\n")


def cmd_assess(out_dir: Path, manifest_path: Path) -> dict:
    path = out_dir / "readiness.json"
    if path.exists():
        sys.exit(f"{path} already exists; readiness assessment is one-touch")
    verdict = assess_manifest(load_manifest(manifest_path))
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2) + "\n")
    (out_dir / "report.md").write_text(render_report(verdict))
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="experiments/newdata")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("candidates", help="write the frozen candidate data classes")

    reg = sub.add_parser("register", help="freeze provider and data class")
    reg.add_argument("--provider", required=True)
    reg.add_argument("--data-class", required=True, choices=DATA_CLASSES)

    assess = sub.add_parser("assess", help="assess an offline provider manifest")
    assess.add_argument("--manifest", required=True)

    args = parser.parse_args()
    out_dir = Path(args.out)
    if args.command == "candidates":
        cmd_candidates(out_dir)
    elif args.command == "register":
        cmd_register(out_dir, args.provider, args.data_class)
    else:
        verdict = cmd_assess(out_dir, Path(args.manifest))
        print(f"[{verdict['status']}] {verdict['provider']} {verdict['data_class']}")


if __name__ == "__main__":
    main()
