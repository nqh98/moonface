# src/moonface/research/bb_harvest.py
"""Bollinger-breakout HARVEST test — can the diagnostic drift be traded?

The exit-free `bb_breakout` decomposition (experiments/bb_breakout) found real,
CI-clean positive forward drift after an upper/lower band cross on BTC 4h. This
lane asks the only question that matters for a deployable long/short signal:
does that drift survive an EXIT, real cost, an OOS split, and a drawdown budget?

It is a thin, frozen wrapper over the pre-registered 3-stage `edge_search` gate
(Stouffer Z gross -> deflated Sharpe net -> economic-bar walk-forward). Nothing
about the gate is relaxed: DSR is deflated against the FULL cell count tried
here (n_trials = len(cells)), so the breadth of the entry x exit grid is paid
for. A NEGATIVE reproduces the standing 'drift is real but unharvestable' wall;
an EDGE is paper-only and would still need cross-asset transfer before live.
Design mirrors the dual-timeframe search; pure module, network IO lives in tools/."""
from __future__ import annotations

from moonface.research.edge_search import Cell, run_cell, to_leaderboard

# 4h walk-forward window convention (matches research/system_cells _TEST_BARS).
_TEST_BARS = 500
_STEP_BARS = 250
_H = 24                 # declump / prescreen horizon (4 days on 4h), mid of the
#                         productive 6..30-bar range where the diagnostic CIs were
#                         cleanest and widest.

# CI-clean bb_breakout entries from the exit-free decomposition (period=50 was the
# strongest, every horizon excluding zero; period=20/mult=2 clean at h6/h12/h30).
_ENTRIES: list[dict] = [
    {"period": 50, "mult": 2.0},
    {"period": 50, "mult": 2.5},
    {"period": 20, "mult": 2.0},
]

# Frozen exit grid drawn from foundation.exits EXECUTABLE_EXITS (academic set,
# DSR-calibrated). horizon_hold is the faithful fixed-N baseline that the drift
# was measured under; the other three are the 'let it run / survive drawdown'
# levers the program has repeatedly failed to harvest H4 drift with.
_EXITS: list[tuple[str, dict]] = [
    ("horizon_hold", {"n_bars": 24, "atr_period": 14}),
    ("atr_trail", {"k_trail": 3.0, "max_bars": 48, "atr_period": 14}),
    ("breakeven_horizon", {"n_bars": 24, "k_stop": 3.0, "atr_period": 14}),
    ("horizon_wide_stop", {"n_bars": 24, "k_stop": 3.0, "atr_period": 14}),
]


def cells() -> list[Cell]:
    """The frozen entry x exit grid. len(cells) is the DSR n_trials."""
    out: list[Cell] = []
    for entry in _ENTRIES:
        for exit_name, exit_params in _EXITS:
            label = (f"bb_breakout p{entry['period']}m{entry['mult']}"
                     f":{exit_name}")
            out.append(Cell(
                label=label, family="bb_breakout", params=dict(entry),
                exit_name=exit_name, exit_params=dict(exit_params), h=_H,
                test_bars=_TEST_BARS, step_bars=_STEP_BARS, is_retest=False))
    return out


def _cell_oos_sharpe(cell, train_oos_candles) -> float:
    from moonface.core.metrics import _sharpe
    from moonface.research.edge_search import net_trade_rs
    rs = net_trade_rs(train_oos_candles, cell.family, cell.params,
                      cell.exit_name, cell.exit_params, cell.h)
    return _sharpe(rs) if len(rs) >= 2 else 0.0


def run(train_oos_candles, full_candles) -> list[dict]:
    """Run every harvest cell through the frozen gate. DSR is deflated against
    the true number of cells tried here (NOT edge_search's hard-coded 9)."""
    cs = cells()
    n_trials = len(cs)
    trial_srs = [_cell_oos_sharpe(c, train_oos_candles) for c in cs]
    rows = [run_cell(c, train_oos_candles, full_candles, trial_srs, n_trials)
            for c in cs]
    rows.sort(key=lambda r: (r["stage2"]["dsr"] if r["stage2"] else float("-inf")),
              reverse=True)
    return rows


def render_report(rows, symbol, tf, n_bars, holdout_bars) -> str:
    any_edge = any(r["verdict"] == "edge" for r in rows)
    overall = ("EDGE FOUND (paper-only — needs cross-asset transfer)"
               if any_edge else "NEGATIVE")
    lines = [
        f"# Bollinger-Breakout Harvest — {symbol} {tf}", "",
        f"## Verdict: {overall}", "",
        "> Does the CI-clean exit-free bb_breakout drift survive an exit + cost +",
        "> OOS split + drawdown budget? Frozen 3-stage gate (gross Z>=2.0 ->",
        f"> net DSR>=0.95, n_trials={len(rows)} -> economic bar). A NEGATIVE",
        "> reproduces the standing 'drift real, path unharvestable' wall and does",
        "> NOT change the WAIT stance.", "",
        f"- bars: {n_bars}  (holdout last {holdout_bars} reserved for stage 3 only)",
        "",
        "| cell | n | z | dsr | pf | mar | ddR | robust | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for lb in to_leaderboard(rows):
        lines.append(
            f"| {lb['label']} | {lb['n1']} | {_f(lb['z'])} | {_f(lb['dsr'])} | "
            f"{_f(lb['econ_pf'])} | {_f(lb['econ_mar'])} | {_f(lb['econ_dd'])} | "
            f"{_f(lb['robust_frac'])} | {lb['verdict']} |")
    return "\n".join(lines) + "\n"


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))
