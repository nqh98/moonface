"""Pre-registered, read-only backtest evaluation of the regime-conditional MoE."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from moonface.data.bundle import load_bundle
from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.models.engine.config import load_engine_config
from moonface.models.engine.moe.config_moe import MoeConfig
from moonface.models.engine.moe.evaluate_moe import build_moe_report
from moonface.models.engine.moe.experts import (
    default_experts,
    mechanism_experts,
    orthogonal_experts,
)
from moonface.models.engine.repair import PURGE_MS
from moonface.models.engine.v3.config_v3 import EngineConfigV3
from moonface.models.engine.v3.evaluate import ASSETS, SEALED_START_TS_MS

_EXPERT_SETS = {
    "price": mechanism_experts,
    "ortho": orthogonal_experts,
    "all": default_experts,
}

# ETH/SOL only ever contribute to gate3_transfer, which is evaluated solely
# within the sealed window -- W is fit on BTC alone. Fetching their full
# 2020-> history is both wasteful and can trip the coverage floor on assets
# whose OI archive starts later than BTC's; narrow their fetch to what the
# transfer test can actually use (sealed window + lookback + purge + margin).
_TRANSFER_ONLY_ASSETS = frozenset({"ETH", "SOL"})
_TRANSFER_FETCH_MARGIN_MS = 90 * 86_400_000


def _moe_asset(key: str) -> dict:
    asset = dict(ASSETS[key])
    asset["funding_symbol"] = asset["symbol"]
    asset["metrics_field"] = "sum_open_interest"
    return asset


def _bundle_start_ms(key: str, args: argparse.Namespace) -> int:
    if key not in _TRANSFER_ONLY_ASSETS:
        return args.start_ms
    timeframe_ms = TIMEFRAME_MS[_moe_asset(key)["timeframe"]]
    transfer_start = (
        SEALED_START_TS_MS - PURGE_MS - args.lookback * timeframe_ms - _TRANSFER_FETCH_MARGIN_MS
    )
    return max(args.start_ms, transfer_start)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="moe-evaluate")
    parser.add_argument("--v22-engine", default="promotion/engine.json")
    parser.add_argument("--start-ms", type=int, required=True)
    parser.add_argument("--end-ms", type=int, required=True)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--warmup", type=int, default=6000)
    parser.add_argument("--lookback", type=int, default=400)
    parser.add_argument("--q-confluence", type=int, default=MoeConfig.q_confluence,
                        help="min agreeing weighted experts to ENTER (frozen into moe_hash)")
    parser.add_argument("--experts", choices=["price", "ortho", "all"], default="all",
                        help="expert set (frozen into identity_hash)")
    parser.add_argument("--out", default=None)
    return parser


def run(argv: list[str] | None = None, loaders: dict | None = None) -> int:
    args = build_parser().parse_args(argv)
    load = loaders or {key: load_bundle for key in ASSETS}
    cfg_v22 = load_engine_config(args.v22_engine)
    cfg_v3 = EngineConfigV3()
    cfg_moe = MoeConfig(q_confluence=args.q_confluence)
    experts = _EXPERT_SETS[args.experts]()

    def bundle(key: str):
        return load[key](_moe_asset(key), _bundle_start_ms(key, args), args.end_ms, args.cache_dir)

    report = build_moe_report(
        bundle("BTC"),
        bundle("ETH"),
        bundle("SOL"),
        cfg_v3,
        cfg_v22,
        cfg_moe,
        args.warmup,
        args.lookback,
        experts=experts,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
