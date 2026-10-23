from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from moonface.kernel.store import Store

_FUNNEL_ORDER = ("pending", "screened", "oos_pass", "corrected_survivor",
                 "lockbox_pass", "lockbox_fail", "rejected", "error")


def _fmt(value, places: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return f"{value:.{places}f}"
    return str(value)


def _sort_key(row: dict) -> tuple:
    m = row["stage_results"]
    return (m.get("dsr", float("-inf")), m.get("research_mar", float("-inf")))


def render_domain_report(store: Store, name: str, version: int) -> str:
    d = store.domain(name, version)
    if d is None:
        raise KeyError(f"unknown domain {name} v{version}")
    counts = store.counts(name, version)
    rows = store.rows(name, version)
    lines = [
        f"# Research domain report: {name} v{version}",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- status: {d['status']}",
        f"- grid size: {d['grid_size']}",
        f"- lockbox touched: {d['lockbox_touched']}",
        "",
        "## Funnel",
        "",
        "| status | count |",
        "|---|---|",
    ]
    lines += [f"| {s} | {counts.get(s, 0)} |" for s in _FUNNEL_ORDER]
    scored = sorted((r for r in rows if r["stage_results"]),
                    key=_sort_key, reverse=True)
    lines += [
        "", "## Leaderboard (top 20)", "",
        "| entry | exit | f | screen n | screen exp R | holdout MAR |"
        " research MAR | DSR | tail MAR | status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in scored[:20]:
        spec = json.loads(r["spec_json"])
        m = r["stage_results"]
        lines.append(
            f"| {spec['entry']['family']} {spec['entry']['params']} "
            f"| {spec['exit']['name']} {spec['exit']['params']} "
            f"| {spec['fraction']} | {m.get('screen_trades', '-')} "
            f"| {_fmt(m.get('screen_expectancy_r'))} "
            f"| {_fmt(m.get('holdout_mar'))} | {_fmt(m.get('research_mar'))} "
            f"| {_fmt(m.get('dsr'), 6)} | {_fmt(m.get('tail_mar'))} "
            f"| {r['status']} |")
    lines += ["", "## Decision", ""]
    status = d["status"]
    if status == "awaiting_gate":
        if counts.get("corrected_survivor", 0):
            lines.append(
                f"Corrected survivors await the one-touch lockbox. Review the "
                f"leaderboard, then run: `python tools/research.py gate {name} "
                f"--open-lockbox` followed by `python tools/research.py run`.")
        else:
            lines.append("Stopped for review (errors or empty survivor set). "
                         "Close the domain or register a new version.")
    elif status == "closed_positive":
        lines.append("VALIDATED SURVIVOR(S): see lockbox_pass rows. "
                     "Promotion is a human decision; the program makes no "
                     "trading recommendation.")
    elif status == "closed_negative":
        lines.append("Domain closed negative: no hypothesis cleared the "
                     "pre-committed gates on the lockbox tail.")
    elif status == "blocked":
        lines.append("Blocked: the signal generator for this family is not "
                     "implemented yet.")
    else:
        lines.append("Domain still draining; no decision required.")
    return "\n".join(lines) + "\n"


def write_domain_report(store: Store, name: str, version: int,
                        out_root: Path) -> Path:
    out_dir = out_root / name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report_v{version}.md"
    path.write_text(render_domain_report(store, name, version), encoding="utf-8")
    return path
