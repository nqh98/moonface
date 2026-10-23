"""Leaderboard report: honest markdown + machine-readable JSON."""

from __future__ import annotations

BANNER = (
    "> **DIAGNOSTIC RE-RANK — NOT pre-registered evidence.** Every lane was re-run on one\n"
    "> shared full window; sealed holdouts are conceptually re-opened and the ranking is\n"
    "> winner's-curse biased. Use for orientation only; promotion still requires each\n"
    "> lane's own pre-registered OOS gate."
)

_TABLE_HEADER = (
    "| Rank | Lane | Key | Exp(R) | PF | MaxDD(R) | N | Total(R) | MAR | Signal | Config Src | Exit |\n"
    "|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|"
)

_ROW_COLS = [
    "lane", "key", "expectancy_r", "pf", "max_dd_r",
    "n", "total_r", "mar", "current_signal", "config_source", "exit_name",
]


def _fmt(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def render_markdown(result: dict, asof: str) -> str:
    """Render the diagnostic-re-rank leaderboard as markdown."""
    lines: list[str] = []
    lines.append(BANNER)
    lines.append("")

    # header metadata
    window = result.get("window") or {}
    lines.append(
        f"**asof**: {asof} | "
        f"window: {window.get('start_ms')}–{window.get('end_ms')} | "
        f"btc_bars: {result.get('btc_bars')} | "
        f"btc_sha: {result.get('btc_sha')}"
    )
    lines.append("")
    lines.append(_TABLE_HEADER)

    ok_rows = [r for r in result.get("rows", []) if r.get("status", "ok") == "ok"]
    for rank, row in enumerate(ok_rows, start=1):
        cells = [str(rank)] + [_fmt(row.get(c)) for c in _ROW_COLS]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    # MAR methodology footnote
    lines.append("> _MAR is diagnostic-only and methodology-mixed across lanes (records-carrying lanes use atr_frac-clamped equity; r_stream lanes use a flat 0.01 fraction). Rows are ranked on expectancy_r only._")
    lines.append("")

    # Excluded
    excluded = result.get("excluded", [])
    if excluded:
        lines.append("## Excluded")
        lines.append("")
        for item in excluded:
            lines.append(f"- **{item.get('lane', '?')}**: {item.get('reason', '?')}")
        lines.append("")

    # Errors (only if non-empty)
    errors = result.get("errors", [])
    if errors:
        lines.append("## Errors")
        lines.append("")
        for item in errors:
            lines.append(f"- **{item.get('lane', '?')}**: {item.get('error', '?')}")
        lines.append("")

    return "\n".join(lines)


def render_json(result: dict, asof: str) -> dict:
    """Return the machine-readable diagnostic-re-rank result."""
    return {
        "evidence_class": "diagnostic_rerank",
        "sealed_holdouts": "conceptually_reopened",
        "asof": asof,
        "window": result.get("window"),
        "btc_bars": result.get("btc_bars"),
        "btc_sha": result.get("btc_sha"),
        "rows": result.get("rows", []),
        "excluded": result.get("excluded", []),
        "errors": result.get("errors", []),
    }
