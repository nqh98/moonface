"""Delta-neutral BTC funding-carry accounting (measurement lane).

Descriptive accounting over historical contractual cash flows. Nothing is
predicted, nothing is optimized, no verdict is issued. Frozen conventions
and pinned inputs: experiments/carry_measure/SPEC.md.
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from dataclasses import dataclass

from moonface.kernel.bootstrap import moving_block_resample, percentile

HOUR_MS = 3_600_000
FUNDING_INTERVAL_MS = 8 * HOUR_MS
DAY_MS = 86_400_000
MS_YEAR = 365.25 * DAY_MS

WINDOW_START_MS = 1_577_836_800_000  # 2020-01-01 00:00 UTC
WINDOW_END_MS = 1_782_835_200_000    # 2026-06-30 16:00 UTC (last funding point)

SEED = 20260716
BLOCK_LEN = 90        # bootstrap block: 90 funding intervals = 30 days
N_RESAMPLES = 2000
MARGIN_BUFFER = 0.30  # USDT buffer on the short leg, fraction of notional
CAPITAL_FACTOR = 1.0 + MARGIN_BUFFER
COST_GRID_BPS = (5.0, 10.0, 20.0)
DRIFT_THRESHOLD = 0.10
CONVENTIONS = ("R0", "R1a", "R1b")
REF_CAPITAL_USD = 100_000.0


class GapError(ValueError):
    """A pinned input series is missing points inside the window."""


def _norm_hour(ts_ms: float) -> int:
    """Funding timestamps carry ms jitter (…005); snap to the exact hour."""
    return int(round(ts_ms / HOUR_MS)) * HOUR_MS


def load_funding(path: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """(ts_ms, rate) at strict 8h cadence covering [start_ms, end_ms] exactly."""
    points: list[tuple[int, float]] = []
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = _norm_hour(float(row[0]))
            if start_ms <= ts <= end_ms:
                points.append((ts, float(row[1])))
    if not points:
        raise GapError(f"{path}: no funding points in window")
    if points[0][0] != start_ms:
        raise GapError(f"{path}: first point {points[0][0]} != {start_ms}")
    if points[-1][0] != end_ms:
        raise GapError(f"{path}: last point {points[-1][0]} != {end_ms}")
    for (a, _), (b, _) in zip(points, points[1:]):
        if b - a != FUNDING_INTERVAL_MS:
            raise GapError(f"{path}: {b - a} ms step after {a} (want 8h)")
    return points


def load_bars_1h(path: str, start_ms: int, end_ms: int) -> dict[int, tuple[float, float]]:
    """bar-open ts -> (open, close); contiguous 1h bars covering
    [start_ms, end_ms] inclusive. Missing bars are a GapError — never
    interpolated (repo convention)."""
    bars: dict[int, tuple[float, float]] = {}
    prev: int | None = None
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = int(float(row[0]))
            if ts < start_ms or ts > end_ms:
                continue
            if prev is not None and ts - prev != HOUR_MS:
                raise GapError(f"{path}: {ts - prev} ms step after {prev} (want 1h)")
            prev = ts
            bars[ts] = (float(row[1]), float(row[4]))
    if not bars:
        raise GapError(f"{path}: no bars in window")
    first, last = min(bars), max(bars)
    if first != start_ms:
        raise GapError(f"{path}: first bar {first} != {start_ms}")
    if last != end_ms:
        raise GapError(f"{path}: last bar {last} != {end_ms}")
    return bars


def price_at(bars: dict[int, tuple[float, float]], ts_ms: int) -> float:
    """Price at instant ts = open of the 1h bar opening at ts."""
    try:
        return bars[ts_ms][0]
    except KeyError:
        raise GapError(f"no 1h bar opening at {ts_ms}") from None


@dataclass(frozen=True)
class LedgerRow:
    ts_ms: int
    rate: float
    price: float
    q_btc: float
    funding_usd: float   # + = received by the short perp leg
    cost_usd: float      # entry/exit/resize costs charged at this timestamp
    net_usd: float
    cum_net_usd: float


def _month_key(ts_ms: int) -> tuple[int, int]:
    d = dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc)
    return d.year, d.month


def run_ledger(funding: list[tuple[int, float]],
               bars: dict[int, tuple[float, float]],
               convention: str, cost_bps: float,
               n0: float = 1.0) -> list[LedgerRow]:
    """One pass over the funding grid for one convention and one cost level.

    Conventions (SPEC §1): R0 = BTC-units hedge entered once, never resized.
    R1a = resize both legs to n0 on the first funding timestamp of each new
    calendar month. R1b = resize when |q*P - n0|/n0 > DRIFT_THRESHOLD.
    Funding accrues on the quantity held entering the interval; resizes
    execute right after the funding snapshot.
    """
    if convention not in CONVENTIONS:
        raise ValueError(f"unknown convention {convention!r}")
    per_leg = (cost_bps / 2.0) / 10_000.0
    p0 = price_at(bars, funding[0][0])
    q = n0 / p0
    cum = 0.0
    rows: list[LedgerRow] = []
    for i, (ts, rate) in enumerate(funding):
        price = price_at(bars, ts)
        funding_usd = rate * q * price
        cost = 0.0
        if i == 0:
            cost += 2.0 * per_leg * n0  # entry: both legs at full notional
        resize = False
        if convention == "R1a" and i > 0 and _month_key(ts) != _month_key(funding[i - 1][0]):
            resize = True
        elif convention == "R1b" and abs(q * price - n0) / n0 > DRIFT_THRESHOLD:
            resize = True
        if resize:
            q_new = n0 / price
            cost += 2.0 * per_leg * abs(q_new - q) * price
            q = q_new
        if i == len(funding) - 1:
            cost += 2.0 * per_leg * (q * price)  # exit: both legs
        net = funding_usd - cost
        cum += net
        rows.append(LedgerRow(ts, rate, price, q, funding_usd, cost, net, cum))
    return rows


@dataclass(frozen=True)
class Episode:
    start_ts: int
    end_ts: int
    n_intervals: int
    depth_rate_sum: float  # sum of the run's (negative) rates


def negative_episodes(funding: list[tuple[int, float]]) -> list[Episode]:
    """Maximal runs of consecutive strictly-negative funding intervals."""
    episodes: list[Episode] = []
    start: int | None = None
    last = 0
    depth = 0.0
    n = 0
    for ts, rate in funding:
        if rate < 0:
            if start is None:
                start, depth, n = ts, 0.0, 0
            depth += rate
            n += 1
            last = ts
        elif start is not None:
            episodes.append(Episode(start, last, n, depth))
            start = None
    if start is not None:
        episodes.append(Episode(start, last, n, depth))
    return episodes



def _sum_by(keys: list[tuple[int, int]], gross: list[float],
            net: list[float]) -> list[tuple[int, int, float, float]]:
    out: list[tuple[int, int, float, float]] = []
    for key, g, n in zip(keys, gross, net):
        if out and (out[-1][0], out[-1][1]) == key:
            y, m, cg, cn = out[-1]
            out[-1] = (y, m, cg + g, cn + n)
        else:
            out.append((key[0], key[1], g, n))
    return out


def monthly_sums(rows: list[LedgerRow]) -> list[tuple[int, int, float, float]]:
    return _sum_by([_month_key(r.ts_ms) for r in rows],
                   [r.funding_usd for r in rows], [r.net_usd for r in rows])


def quarterly_sums(rows: list[LedgerRow]) -> list[tuple[int, int, float, float]]:
    keys = [(y, (m - 1) // 3 + 1) for y, m in (_month_key(r.ts_ms) for r in rows)]
    return _sum_by(keys, [r.funding_usd for r in rows], [r.net_usd for r in rows])


def monthly_rate_sums(funding: list[tuple[int, float]]) -> list[tuple[int, int, float]]:
    sums = _sum_by([_month_key(ts) for ts, _ in funding],
                   [r for _, r in funding], [0.0] * len(funding))
    return [(y, m, g) for y, m, g, _ in sums]


def _sample_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return var ** 0.5


def yearly_rate_stats(funding: list[tuple[int, float]]) -> list[dict]:
    monthly = monthly_rate_sums(funding)
    out: list[dict] = []
    for year in sorted({_month_key(ts)[0] for ts, _ in funding}):
        rates = [r for ts, r in funding if _month_key(ts)[0] == year]
        months_pct = [s * 100 for y, _, s in monthly if y == year]
        mean_rate = sum(rates) / len(rates)
        out.append({"year": year, "n": len(rates), "mean_rate": mean_rate,
                    "ann_pct": mean_rate * 3 * 365 * 100,
                    "monthly_mean_pct": sum(months_pct) / len(months_pct),
                    "monthly_std_pct": _sample_std(months_pct)})
    return out


def drawdown_stats(ts: list[int], cum: list[float]) -> dict:
    """Max drawdown and longest time-under-water of a cumulative curve.
    Baseline equity is 0 before the first point (entry costs count)."""
    peak = 0.0
    peak_ts = ts[0]
    max_dd = 0.0
    dd_peak_ts = ts[0]
    dd_trough_ts = ts[0]
    last_high_ts = ts[0]
    longest_uw_ms = 0
    for t, c in zip(ts, cum):
        if c >= peak:
            peak = c
            peak_ts = t
            longest_uw_ms = max(longest_uw_ms, t - last_high_ts)
            last_high_ts = t
        dd = peak - c
        if dd > max_dd:
            max_dd = dd
            dd_peak_ts = peak_ts
            dd_trough_ts = t
    longest_uw_ms = max(longest_uw_ms, ts[-1] - last_high_ts)
    return {"max_dd": max_dd, "peak_ts": dd_peak_ts, "trough_ts": dd_trough_ts,
            "longest_uw_days": longest_uw_ms / DAY_MS}


def _max_dd_of(net: list[float]) -> float:
    cum = 0.0
    peak = 0.0
    dd = 0.0
    for x in net:
        cum += x
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def block_bootstrap_dd(net: list[float], block_len: int = BLOCK_LEN,
                       n_resamples: int = N_RESAMPLES,
                       seed: int = SEED) -> tuple[float, float]:
    """(p5, p95) of max drawdown over block-bootstrap resamples of the
    per-interval net cashflow series. Fixed seed (SPEC §2 Q4)."""
    if len(net) <= block_len:
        raise ValueError("series shorter than bootstrap block")
    rng = random.Random(seed)
    dds: list[float] = []
    for _ in range(n_resamples):
        sample = moving_block_resample(rng, net, block_len)
        dds.append(_max_dd_of(sample))
    return percentile(dds, 5), percentile(dds, 95)


def max_runup(marks: list[tuple[int, float]]) -> tuple[float, int, int]:
    lo = marks[0][1]
    lo_ts = marks[0][0]
    best = 0.0
    best_t0 = best_t1 = marks[0][0]
    for t, p in marks:
        if p < lo:
            lo, lo_ts = p, t
        r = p / lo - 1.0
        if r > best:
            best, best_t0, best_t1 = r, lo_ts, t
    return best, best_t0, best_t1


def runup_windows(marks: list[tuple[int, float]],
                  window_days: tuple[int, ...] = (7, 14, 30, 60, 90)) -> dict[int, float]:
    out: dict[int, float] = {}
    for days in window_days:
        w = days * 3  # 8h marks per day
        best = 0.0
        for i in range(len(marks)):
            window_lo = min(p for _, p in marks[max(0, i - w + 1):i + 1])
            best = max(best, marks[i][1] / window_lo - 1.0)
        out[days] = best
    return out


def basis_series(perp_bars: dict[int, tuple[float, float]],
                 spot_bars: dict[int, tuple[float, float]],
                 start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """Hourly spot-perp basis (perp_close - spot_close) / spot_close.
    Descriptive only (Q5); never enters the P&L curve (SPEC §3)."""
    out: list[tuple[int, float]] = []
    ts = start_ms
    while ts <= end_ms:
        try:
            perp_close = perp_bars[ts][1]
            spot_close = spot_bars[ts][1]
        except KeyError:
            raise GapError(f"missing 1h bar at {ts} for basis") from None
        out.append((ts, (perp_close - spot_close) / spot_close))
        ts += HOUR_MS
    return out


def basis_haircuts(basis_values: list[float]) -> dict:
    """Entry (sell perp/buy spot) is hurt by negative basis; exit (buy perp/
    sell spot) by positive basis. Floored at zero: a favorable basis is not
    reported as a negative cost (conservative reading, SPEC §5-bias)."""
    p5 = percentile(basis_values, 5)
    p50 = percentile(basis_values, 50)
    p95 = percentile(basis_values, 95)
    return {"entry_median_bps": max(0.0, -p50) * 10_000,
            "entry_p5_adverse_bps": max(0.0, -p5) * 10_000,
            "exit_median_bps": max(0.0, p50) * 10_000,
            "exit_p95_adverse_bps": max(0.0, p95) * 10_000}


def ascii_histogram(values: list[float], n_bins: int = 12, width: int = 40) -> str:
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    bins = [0] * n_bins
    for v in values:
        bins[min(int((v - lo) / span * n_bins), n_bins - 1)] += 1
    peak = max(bins)
    lines = []
    for k, count in enumerate(bins):
        a = lo + span * k / n_bins
        b = lo + span * (k + 1) / n_bins
        bar = "#" * (round(count / peak * width) if count else 0)
        lines.append(f"{a:9.3f} .. {b:9.3f} | {bar} {count}")
    return "\n".join(lines)


def _iso(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def assemble_results(funding: list[tuple[int, float]],
                     perp_bars: dict[int, tuple[float, float]],
                     spot_bars: dict[int, tuple[float, float]]) -> dict:
    """All Q1-Q7 computations, one pass, no selection anywhere."""
    start_ms, end_ms = funding[0][0], funding[-1][0]
    years = (end_ms - start_ms) / MS_YEAR

    # Q1 — gross carry in rate space (% of currently-held notional; exact
    # for every convention because funding is charged on current notional).
    yearly = yearly_rate_stats(funding)
    monthly_gross_pct = [s * 100 for _, _, s in monthly_rate_sums(funding)]
    q1 = {"yearly": yearly, "monthly_gross_pct": monthly_gross_pct,
          "histogram": ascii_histogram(monthly_gross_pct)}

    # Q2 — net carry grid, conventions x cost levels, both capital bases.
    q2 = []
    for conv in CONVENTIONS:
        for bps in COST_GRID_BPS:
            rows = run_ledger(funding, perp_bars, conv, bps)
            total = rows[-1].cum_net_usd
            q2.append({"convention": conv, "cost_bps": bps,
                       "total_net_pct_notional": total * 100,
                       "ann_net_pct_notional": total / years * 100,
                       "ann_net_pct_capital": total / years / CAPITAL_FACTOR * 100})

    # Q3 — negative-funding episodes.
    episodes = negative_episodes(funding)
    durations = [float(e.n_intervals) for e in episodes]
    deepest = sorted(episodes, key=lambda e: e.depth_rate_sum)[:5]
    q3 = {"count": len(episodes),
          "longest_run_intervals": int(max(durations)) if durations else 0,
          "duration_p50": percentile(durations, 50) if durations else 0.0,
          "duration_p90": percentile(durations, 90) if durations else 0.0,
          "deepest": [{"start": _iso(e.start_ts), "end": _iso(e.end_ts),
                       "n_intervals": e.n_intervals,
                       "depth_pct_notional": e.depth_rate_sum * 100}
                      for e in deepest]}

    # Q4 — drawdown of the net curve at the 10 bps cell, per convention.
    q4 = {}
    for conv in CONVENTIONS:
        rows = run_ledger(funding, perp_bars, conv, 10.0)
        stats = drawdown_stats([r.ts_ms for r in rows], [r.cum_net_usd for r in rows])
        ci_lo, ci_hi = block_bootstrap_dd([r.net_usd for r in rows])
        ann = rows[-1].cum_net_usd / years
        q4[conv] = {"max_dd_pct_notional": stats["max_dd"] * 100,
                    "dd_peak": _iso(stats["peak_ts"]),
                    "dd_trough": _iso(stats["trough_ts"]),
                    "longest_underwater_days": stats["longest_uw_days"],
                    "max_dd_over_avg_annual_carry":
                        (stats["max_dd"] / ann) if ann > 0 else None,
                    "dd_ci90_pct_notional": [ci_lo * 100, ci_hi * 100]}

    # Q5 — descriptive basis percentiles and boundary haircuts.
    basis = basis_series(perp_bars, spot_bars, start_ms, end_ms)
    values = [b for _, b in basis]
    by_year: dict[int, list[float]] = {}
    for ts, b in basis:
        by_year.setdefault(_month_key(ts)[0], []).append(b)
    q5 = {"percentiles_bps": {str(p): percentile(values, p) * 10_000
                              for p in (1, 5, 25, 50, 75, 95, 99)},
          "by_year_bps": {str(y): {str(p): percentile(v, p) * 10_000
                                   for p in (5, 50, 95)}
                          for y, v in sorted(by_year.items())},
          "haircuts": basis_haircuts(values)}

    # Q6 — Q1's yearly gross restated in isolation ("is this shrinking?").
    q6 = [{"year": r["year"], "n": r["n"], "ann_gross_pct": r["ann_pct"]}
          for r in yearly]

    # Q7 — worst month/quarter at the 10 bps cell, in plain numbers.
    n0_usd = REF_CAPITAL_USD / CAPITAL_FACTOR
    q7 = {}
    for conv in CONVENTIONS:
        rows = run_ledger(funding, perp_bars, conv, 10.0)
        months = monthly_sums(rows)
        quarters = quarterly_sums(rows)
        wm = min(months, key=lambda x: x[3])
        wq = min(quarters, key=lambda x: x[3])
        q7[conv] = {"worst_month": {"label": f"{wm[0]}-{wm[1]:02d}",
                                    "net_pct_notional": wm[3] * 100,
                                    "net_usd_on_100k_capital": wm[3] * n0_usd},
                    "worst_quarter": {"label": f"{wq[0]}-Q{wq[1]}",
                                      "net_pct_notional": wq[3] * 100,
                                      "net_usd_on_100k_capital": wq[3] * n0_usd}}

    # Run-ups feed the liquidation-risk prose (margin buffer context).
    marks = [(ts, price_at(perp_bars, ts)) for ts, _ in funding]
    runup, t0, t1 = max_runup(marks)
    runups = {"max_runup_pct": runup * 100,
              "max_runup_from": _iso(t0), "max_runup_to": _iso(t1),
              "windows_pct": {str(d): r * 100
                              for d, r in runup_windows(marks).items()}}

    return {"window": {"start": _iso(start_ms), "end": _iso(end_ms),
                       "start_ms": start_ms, "end_ms": end_ms, "years": years},
            "q1": q1, "q2": q2, "q3": q3, "q4": q4, "q5": q5, "q6": q6,
            "q7": q7, "runups": runups}


def render_results_md(results: dict, meta: dict) -> str:
    w = results["window"]
    lines: list[str] = []
    add = lines.append
    add("# carry_measure — RESULTS")
    add("")
    add("Descriptive accounting of a delta-neutral BTC funding-carry position")
    add("(long 1x spot / short 1x BTCUSDT USDS-M perp). Nothing here is a")
    add("forecast; see experiments/carry_measure/SPEC.md for every convention.")
    add("")
    add(f"- pipeline commit: `{meta['commit']}`")
    add(f"- bootstrap seed: {meta['seed']}")
    for name, info in meta["inputs_sha256"].items():
        add(f"- input `{name}`: `{info['path']}` sha256 `{info['sha256']}`")
    add(f"- window: {w['start']} -> {w['end']} UTC ({w['years']:.2f} years)")
    add(f"- margin buffer: {MARGIN_BUFFER:.0%} of notional; total capital = notional x {CAPITAL_FACTOR:.2f}")
    add("- cost convention: quoted round-trip bps = one leg's in+out; a single trade")
    add("  on one leg costs half the quoted bps; entry, exit and resizes trade both")
    add("  legs (full position in-and-out therefore costs 2x the quoted bps).")
    add("- funding is received at every 8h timestamp incl. the first; mark proxy =")
    add("  open of the 1h bar at the funding timestamp.")
    add("")
    notes = meta.get("notes", [])
    if notes:
        add("## Data provenance notes")
        add("")
        for note in notes:
            add(f"- {note}")
        add("")
    add("## Q1 — gross carry (rate space, % of held notional)")
    add("")
    add("| year | intervals | annualized gross % | monthly mean % | monthly std % |")
    add("|---|---|---|---|---|")
    for r in results["q1"]["yearly"]:
        add(f"| {r['year']} | {r['n']} | {r['ann_pct']:.2f} | "
            f"{r['monthly_mean_pct']:.3f} | {r['monthly_std_pct']:.3f} |")
    add("")
    add("Monthly gross carry, % of notional:")
    add("")
    add("```")
    add(results["q1"]["histogram"])
    add("```")
    add("")
    add("## Q2 — net carry grid (annualized %, after costs)")
    add("")
    add("| convention | cost (bps rt) | ann. net % of notional | ann. net % of capital |")
    add("|---|---|---|---|")
    for cell in results["q2"]:
        add(f"| {cell['convention']} | {cell['cost_bps']:.0f} | "
            f"{cell['ann_net_pct_notional']:.2f} | {cell['ann_net_pct_capital']:.2f} |")
    add("")
    add("## Q3 — negative-funding episodes")
    add("")
    q3 = results["q3"]
    add(f"- episodes: {q3['count']}; longest run: {q3['longest_run_intervals']} "
        f"consecutive 8h intervals; median duration {q3['duration_p50']:.1f}, "
        f"p90 {q3['duration_p90']:.1f} intervals")
    if q3["deepest"]:
        add("")
        add("| deepest episodes | start (UTC) | end (UTC) | intervals | depth % of notional |")
        add("|---|---|---|---|---|")
        for i, e in enumerate(q3["deepest"], 1):
            add(f"| #{i} | {e['start']} | {e['end']} | {e['n_intervals']} | "
                f"{e['depth_pct_notional']:.3f} |")
    add("")
    add("## Q4 — drawdown of the cumulative net curve (10 bps cell)")
    add("")
    add("| convention | max DD % of notional | DD 90% CI (bootstrap) | peak | trough | longest underwater (days) | DD / avg annual carry |")
    add("|---|---|---|---|---|---|---|")
    for conv in CONVENTIONS:
        c = results["q4"][conv]
        ratio = ("n/a" if c["max_dd_over_avg_annual_carry"] is None
                 else f"{c['max_dd_over_avg_annual_carry']:.2f}x")
        ci = c["dd_ci90_pct_notional"]
        add(f"| {conv} | {c['max_dd_pct_notional']:.3f} | "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {c['dd_peak']} | {c['dd_trough']} | "
            f"{c['longest_underwater_days']:.0f} | {ratio} |")
    add("")
    add("## Q5 — spot-perp basis at position boundaries (descriptive)")
    add("")
    add("Full-window hourly basis percentiles, bps:")
    add("")
    add("| p1 | p5 | p25 | p50 | p75 | p95 | p99 |")
    add("|---|---|---|---|---|---|---|")
    p = results["q5"]["percentiles_bps"]
    add("| " + " | ".join(f"{p[str(k)]:.1f}" for k in (1, 5, 25, 50, 75, 95, 99)) + " |")
    add("")
    add("| year | p5 bps | p50 bps | p95 bps |")
    add("|---|---|---|---|")
    for year, row in results["q5"]["by_year_bps"].items():
        add(f"| {year} | {row['5']:.1f} | {row['50']:.1f} | {row['95']:.1f} |")
    add("")
    h = results["q5"]["haircuts"]
    add(f"- entry haircut (sell perp/buy spot): median {h['entry_median_bps']:.1f} bps, "
        f"5th-pct-adverse {h['entry_p5_adverse_bps']:.1f} bps")
    add(f"- exit haircut (buy perp/sell spot): median {h['exit_median_bps']:.1f} bps, "
        f"95th-pct-adverse {h['exit_p95_adverse_bps']:.1f} bps")
    add("- haircuts are not folded into Q2; they are boundary costs to read next to it.")
    add("")
    add("## Q6 — year-by-year gross carry: is this shrinking?")
    add("")
    add("| year | intervals | annualized gross % |")
    add("|---|---|---|")
    for r in results["q6"]:
        add(f"| {r['year']} | {r['n']} | {r['ann_gross_pct']:.2f} |")
    add("")
    add("No trend is fitted and nothing is extrapolated; the table is the answer.")
    add("")
    add("## Q7 — worst month and worst quarter (10 bps cell)")
    add("")
    add(f"Plain-dollar figures are on ${REF_CAPITAL_USD:,.0f} of total capital")
    add(f"(notional ${REF_CAPITAL_USD / CAPITAL_FACTOR:,.0f} + margin buffer).")
    add("")
    add("| convention | worst month | net % | net $ | worst quarter | net % | net $ |")
    add("|---|---|---|---|---|---|---|")
    for conv in CONVENTIONS:
        c = results["q7"][conv]
        wm, wq = c["worst_month"], c["worst_quarter"]
        add(f"| {conv} | {wm['label']} | {wm['net_pct_notional']:.3f} | "
            f"{wm['net_usd_on_100k_capital']:+,.0f} | {wq['label']} | "
            f"{wq['net_pct_notional']:.3f} | {wq['net_usd_on_100k_capital']:+,.0f} |")
    add("")
    add("## Risks (read before acting on any number above)")
    add("")
    ru = results["runups"]
    add("1. **Exchange/counterparty tail risk.** Both legs sit on one venue. An")
    add("   exchange failure is a total-position event that no table above prices.")
    add("   This risk is stated, not quantified — historical funding data contains")
    add("   no information about it.")
    add(f"2. **Liquidation risk on the short perp leg.** With a {MARGIN_BUFFER:.0%} USDT")
    add("   buffer and no top-ups, the short leg is exhausted by a rally of about")
    add(f"   {MARGIN_BUFFER:.0%} before maintenance margin. In this window the largest")
    add(f"   price run-up was {ru['max_runup_pct']:.1f}% ({ru['max_runup_from']} -> "
        f"{ru['max_runup_to']}).")
    add("   Largest run-up inside a trailing window (how fast top-ups must arrive):")
    add("")
    add("   | window (days) | max run-up % |")
    add("   |---|---|")
    for days, r in results["runups"]["windows_pct"].items():
        add(f"   | {days} | {r:.1f} |")
    add("")
    add("   The spot leg gains what the perp leg loses, but spot gains are not")
    add("   automatically usable as perp margin unless collateral is arranged that")
    add("   way; sloppy margin management converts a hedged position into a")
    add("   liquidation.")
    add("3. **Stablecoin/collateral risk.** The margin buffer and funding receipts")
    add("   are USDT-denominated; a USDT break is a correlated loss on the buffer")
    add("   and the carry stream.")
    add("4. **Spot custody/borrow assumptions.** The accounting assumes spot is")
    add("   bought with own capital and held on-venue; no borrow cost and no")
    add("   custody yield. Off-venue custody reduces counterparty exposure but")
    add("   slows margin top-ups (see risk 2).")
    add("5. **Decay.** The Q6 table is the record; the past level of carry is not")
    add("   a promise about its future level.")
    add("")
    add("## Plain-language summary")
    add("")
    grid = {(c["convention"], c["cost_bps"]): c for c in results["q2"]}
    mid = grid[("R0", 10.0)]
    worst_cell = min(results["q2"], key=lambda c: c["ann_net_pct_capital"])
    best_cell = max(results["q2"], key=lambda c: c["ann_net_pct_capital"])
    q4_r0 = results["q4"]["R0"]
    add(f"Over {w['years']:.1f} years a delta-neutral BTC carry position earned a")
    add("gross funding stream that, at the middle cost assumption (R0, 10 bps),")
    add(f"nets to about {mid['ann_net_pct_notional']:.1f}% per year on notional")
    add(f"({mid['ann_net_pct_capital']:.1f}% on total capital including the margin")
    add("buffer). Across all stated conventions and cost levels the annualized")
    add(f"net range was {worst_cell['ann_net_pct_capital']:.1f}% to")
    add(f"{best_cell['ann_net_pct_capital']:.1f}% on capital. The funding stream was")
    add(f"negative in {results['q3']['count']} distinct episodes (longest")
    add(f"{results['q3']['longest_run_intervals']} consecutive 8h intervals), the")
    add("worst month and quarter are in Q7, and the deepest drawdown of the net")
    add(f"curve was {q4_r0['max_dd_pct_notional']:.2f}% of notional with")
    add(f"{q4_r0['longest_underwater_days']:.0f} days as the longest stretch under a")
    add("prior high. The year-by-year table (Q6) shows whether the carry level is")
    add("shrinking; it is reported without extrapolation.")
    add("")
    add("This is input to a personal investment decision, not a research verdict.")
    add("")
    return "\n".join(lines)
