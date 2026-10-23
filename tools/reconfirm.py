"""Quarterly multi-timeframe reconfirmation CLI (registration v1).

Report-only: writes experiments/reconfirmation/<UTC ts>/{report.md,
results.json} and exits 0 (4h ALIVE, anchor intact), 1 (human attention),
or 2 (data error — no partial verdicts). Never writes promotion/."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from moonface.data.ohlcv import TIMEFRAME_MS                  # noqa: E402
from moonface.data.bundle import load_bundle                 # noqa: E402
from moonface.research.reconfirm import (ANCHOR_TIMEFRAME,       # noqa: E402
                                         TIMEFRAMES, anchor_breached,
                                         build_report, measure_timeframe,
                                         verdict)

ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT"}
WINDOW_DAYS = 1095
STALE_LIMIT_INTERVALS = 2


def _now_ms() -> int:
    return int(time.time() * 1000)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reconfirm",
        description="Multi-timeframe reconfirmation (registration v1)."
                    " Report-only; never writes promotion/.")
    p.add_argument("--out", default="experiments/reconfirmation")
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--json", action="store_true", dest="as_json")
    return p


def _prev_last_ts(out_dir: Path) -> dict[str, int]:
    """last_bar_ts per timeframe from the most recent prior results.json."""
    runs = sorted(d for d in out_dir.iterdir()
                  if d.is_dir() and (d / "results.json").exists()) \
        if out_dir.exists() else []
    if not runs:
        return {}
    data = json.loads((runs[-1] / "results.json").read_text())
    return {tf: r["last_bar_ts"] for tf, r in data["timeframes"].items()}


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out)
    prev = _prev_last_ts(out_dir)
    now = _now_ms()
    results = {}
    for tf in TIMEFRAMES:
        tf_ms = TIMEFRAME_MS[tf]
        end_ms = (now // tf_ms) * tf_ms
        start_ms = end_ms - WINDOW_DAYS * 86_400_000
        try:
            bundle = load_bundle({**ASSET, "timeframe": tf}, start_ms,
                                 end_ms, args.cache_dir)
        except Exception as exc:  # noqa: BLE001 - report, never fake a verdict
            print(f"ERROR: {tf} fetch failed: {exc!r}", file=sys.stderr)
            return 2
        if (not bundle.candles
                or bundle.candles[-1].timestamp_ms
                < end_ms - STALE_LIMIT_INTERVALS * tf_ms):
            print(f"ERROR: {tf} series is stale", file=sys.stderr)
            return 2
        results[tf] = measure_timeframe(tf, bundle.candles,
                                        prev_last_ts=prev.get(tf))

    stamp = datetime.fromtimestamp(now / 1000, tz=timezone.utc)
    meta = {"generated_utc": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asset": ASSET, "window_days": WINDOW_DAYS}
    markdown, data = build_report(results, meta)

    run_dir = out_dir / stamp.strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.md").write_text(markdown)
    (run_dir / "results.json").write_text(json.dumps(data, indent=2,
                                                     sort_keys=True))

    if args.as_json:
        print(json.dumps(data, sort_keys=True))
    else:
        print(markdown)
        print(f"written: {run_dir}")
    ok = (verdict(results[ANCHOR_TIMEFRAME]) == "ALIVE"
          and not anchor_breached(results[ANCHOR_TIMEFRAME]))
    return 0 if ok else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
