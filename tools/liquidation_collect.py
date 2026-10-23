#!/usr/bin/env python
"""Binance USD-M liquidation-feed forward collector CLI (Lane 3, Track B).

`collect` subscribes to the live liquidation WebSocket and appends normalized
rows to a durable CSV until interrupted; `status` prints collection stats. Data
acquisition only — no signal/alpha work. There is NO free liquidation archive
and the live feed is throttled to 1 order/sec/symbol, so magnitude during a
cascade is undercounted. Run under a supervisor (systemd/cron-respawn):

  * * * * * cd <repo> && flock -n /tmp/liq_collector.lock \
      .venv/bin/python tools/liquidation_collect.py collect >> watch.log 2>&1

(Do NOT use a `pgrep -f ... ||` watchdog: the cron wrapper shell's own command
line contains this script's name, so pgrep matches the wrapper and the restart
branch never fires. flock cannot self-match.)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.collect.liquidation import (
    append_rows, rows_from_liquidations, snapshot_stats, write_manifest)

SYMBOL = "BTC/USDT:USDT"
ARCHIVE_SYMBOL = "BTCUSDT"


def _csv_path(out_dir: Path) -> Path:
    return out_dir / f"liq_{ARCHIVE_SYMBOL}.csv"


async def _collect(out_dir: Path, flush_every: int) -> int:
    import ccxt.pro as ccxtpro  # noqa: PLC0415 (optional heavy import)
    from ccxt.base.errors import NetworkError  # noqa: PLC0415

    ex = ccxtpro.binance({"options": {"defaultType": "future"}})
    path = _csv_path(out_dir)
    buffered = 0
    try:
        while True:
            try:
                # All-market firehose (!forceOrder@arr), NOT <sym>@forceOrder.
                # The per-symbol channel is far too sparse to keep the ws
                # keepalive fed: the socket timed out on ping-pong, dropped
                # 1006 and reconnected forever without receiving a single
                # event — 16 days, zero rows, no CSV ever created. See
                # docs/findings/COLLECTOR_AUDIT_2026-07-29.md.
                #
                # Pass None, NOT []. ccxt 4.5.56 builds the right subscription
                # for an empty list but then crashes in get_market_from_symbols
                # (`self.market(None)` -> TypeError). None takes the clean
                # early-return path to the same firehose.
                liqs = await ex.watch_liquidations_for_symbols(None)
            except NetworkError as exc:  # covers RequestTimeout; ws drop must not kill the process
                print(f"[liq-collect] ws error, retrying in 5s: {exc}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(5)
                continue
            recv = int(time.time() * 1000)
            # The firehose carries every symbol; the manifest and the readiness
            # gate are BTCUSDT-scoped, so the declared scope is enforced here.
            rows = rows_from_liquidations(liqs, recv, ARCHIVE_SYMBOL)
            if rows:
                append_rows(path, rows)
                buffered += len(rows)
            if buffered >= flush_every:
                write_manifest(out_dir, ARCHIVE_SYMBOL, snapshot_stats(path))
                buffered = 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    finally:
        write_manifest(out_dir, ARCHIVE_SYMBOL, snapshot_stats(path))
        await ex.close()


def cmd_status(out_dir: Path) -> int:
    stats = snapshot_stats(_csv_path(out_dir))
    print(json.dumps(stats, indent=2))
    print("readiness gate (deferred Setup 3): >=6 months AND >= target cascade"
          " clusters — see experiments/newdata/FREE_DATA_FEASIBILITY_liquidations.md")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="experiments/newdata/liquidations")
    p.add_argument("--flush-every", type=int, default=50)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("collect", help="stream liquidations to CSV until interrupted")
    sub.add_parser("status", help="print collection stats + readiness note")
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.command == "collect":
        raise SystemExit(asyncio.run(_collect(out_dir, args.flush_every)))
    raise SystemExit(cmd_status(out_dir))


if __name__ == "__main__":
    main()
