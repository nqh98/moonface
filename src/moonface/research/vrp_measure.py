"""vrp_measure: BTC variance risk premium, measurement lane.

Descriptive accounting over pinned historical data (experiments/vrp_measure/
SPEC.md). Nothing is predicted; there is no verdict and no trading rule here.

Pure functions only: no network imports, no I/O beyond reading the pinned
CSVs. stdlib only -- numpy is an optional pathsig extra and is NOT available.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import random
from dataclasses import dataclass

from moonface.kernel.bootstrap import fixed_block_count_resample, percentile

HOUR_MS = 3_600_000
DAY_MS = 86_400_000
DVOL_INTERVAL_MS = 43_200_000          # 12h
RV_HORIZON_HOURS = 720                 # 30 days
ANNUALIZATION_HOURS = 8760.0           # BTC trades 24/7/365

WINDOW_START_MS = 1_616_544_000_000    # 2021-03-24 00:00 UTC
WINDOW_END_MS = 1_780_228_800_000      # 2026-05-31 12:00 UTC

BLOCK_LEN = 60                         # 60 DVOL points = 30 days
N_RESAMPLES = 2000
BOOTSTRAP_SEED = 20260717
NULL_SEED_GAUSS = 20270101
NULL_SEED_T = 20280101
N_NULL_SEEDS = 500
T_DF = 4
DISJOINT_STRIDE_MS = 30 * DAY_MS

# Binance BTC/USDT spot 1h bars inside this lane's window that are NOT Binance
# data: they are Coinbase BTC/USD candles spliced in under the human-approved
# 2026-07-16 resolution of a real exchange-side gap. Source of truth is
# SPOT_GAP_SUBSTITUTIONS_UTC in tools/carry_measure.py -- duplicated here as
# ms, restricted to this window, because src/ must not import tools/ and
# carry_measure is a frozen run-once lane whose list can no longer change.
# SPEC section 3.3.
SPLICED_BAR_TS_MS = frozenset((
    1618884000000,  # 2021-04-20 02:00
    1618887600000,  # 2021-04-20 03:00
    1619326800000,  # 2021-04-25 05:00
    1619330400000,  # 2021-04-25 06:00
    1619334000000,  # 2021-04-25 07:00
    1628820000000,  # 2021-08-13 02:00
    1628823600000,  # 2021-08-13 03:00
    1628827200000,  # 2021-08-13 04:00
    1628830800000,  # 2021-08-13 05:00
    1632898800000,  # 2021-09-29 07:00
    1632902400000,  # 2021-09-29 08:00
    1679662800000,  # 2023-03-24 13:00
))


class GapError(ValueError):
    """A pinned input series is missing points inside the window."""


def load_dvol(path: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """(ts_ms, dvol_open) at strict 12h cadence covering [start_ms, end_ms].

    Returns the bar OPEN, not the close: Deribit stamps bars at their start,
    so close(t) is not observable until t+12h and using it would look ahead
    into rv_var(t)'s own window (SPEC section 4.1.1). open(t) == close(t-12h),
    so this costs nothing.
    """
    points: list[tuple[int, float]] = []
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = int(float(row[0]))
            if start_ms <= ts <= end_ms:
                points.append((ts, float(row[1])))
    if not points:
        raise GapError(f"{path}: no DVOL points in window")
    for prev, cur in zip(points, points[1:]):
        step = cur[0] - prev[0]
        if step != DVOL_INTERVAL_MS:
            raise GapError(f"{path}: {step} ms step after {prev[0]} (want 12h)")
    if points[0][0] != start_ms:
        raise GapError(f"{path}: first point {points[0][0]} != {start_ms}")
    if points[-1][0] != end_ms:
        raise GapError(f"{path}: last point {points[-1][0]} != {end_ms}")
    return points


def load_spot_closes(path: str, first_ms: int, last_ms: int) -> dict[int, float]:
    """bar-open ts -> close, contiguous 1h bars covering [first_ms, last_ms].

    Missing bars are a GapError -- never interpolated (repo convention).
    """
    closes: dict[int, float] = {}
    prev: int | None = None
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = int(float(row[0]))
            if ts < first_ms or ts > last_ms:
                continue
            if prev is not None and ts - prev != HOUR_MS:
                raise GapError(f"{path}: {ts - prev} ms step after {prev} (want 1h)")
            prev = ts
            closes[ts] = float(row[4])
    if not closes:
        raise GapError(f"{path}: no bars in window")
    first, last = min(closes), max(closes)
    if first != first_ms:
        raise GapError(f"{path}: first bar {first} != {first_ms}")
    if last != last_ms:
        raise GapError(f"{path}: last bar {last} != {last_ms}")
    return closes


@dataclass(frozen=True)
class ReturnSeries:
    """Prefix-summed hourly log returns, splice-aware.

    r2_prefix[k] / cnt_prefix[k] cover returns 0..k-1, so any window is one
    subtraction. Excluded returns contribute 0 to both -- rv_var divides by
    the actual usable count, never by an assumed horizon.
    """

    first_ts: int
    r2_prefix: tuple[float, ...]
    cnt_prefix: tuple[int, ...]

    def index_of(self, ts: int) -> int:
        return (ts - self.first_ts) // HOUR_MS


def usable_mask(first_ret_ts: int, n: int,
                spliced: frozenset[int] = SPLICED_BAR_TS_MS) -> list[bool]:
    """A return stamped `ts` is ln(close(ts)/close(ts-1h)), spanning bars
    ts-1h and ts. It straddles a splice boundary iff exactly one of them is a
    substituted (Coinbase) bar; both-substituted is Coinbase-to-Coinbase and
    is kept (SPEC section 3.3)."""
    out: list[bool] = []
    for i in range(n):
        ts = first_ret_ts + i * HOUR_MS
        out.append((ts in spliced) == ((ts - HOUR_MS) in spliced))
    return out


def build_return_series_from_returns(returns: list[float], first_ret_ts: int,
                                     usable: list[bool]) -> ReturnSeries:
    if len(returns) != len(usable):
        raise ValueError(f"{len(returns)} returns vs {len(usable)} mask entries")
    r2 = [0.0]
    cnt = [0]
    for r, ok in zip(returns, usable):
        r2.append(r2[-1] + (r * r if ok else 0.0))
        cnt.append(cnt[-1] + (1 if ok else 0))
    return ReturnSeries(first_ret_ts, tuple(r2), tuple(cnt))


def build_return_series(closes: dict[int, float], first_ret_ts: int,
                        last_ret_ts: int,
                        spliced: frozenset[int] = SPLICED_BAR_TS_MS) -> ReturnSeries:
    """Hourly log returns stamped first_ret_ts..last_ret_ts inclusive.

    The return stamped `ts` is ln(close(ts)/close(ts-1h)) and covers
    (ts, ts+1h], so close(first_ret_ts - 1h) must be present.
    """
    n = (last_ret_ts - first_ret_ts) // HOUR_MS + 1
    returns: list[float] = []
    for i in range(n):
        ts = first_ret_ts + i * HOUR_MS
        try:
            cur, prev = closes[ts], closes[ts - HOUR_MS]
        except KeyError as exc:
            raise GapError(f"missing spot close at {exc.args[0]}") from exc
        if cur <= 0.0 or prev <= 0.0:
            raise GapError(f"non-positive close at {ts}")
        returns.append(math.log(cur / prev))
    return build_return_series_from_returns(returns, first_ret_ts,
                                            usable_mask(first_ret_ts, n, spliced))


def rv_var(series: ReturnSeries, t: int, horizon: int = RV_HORIZON_HOURS) -> float:
    """Annualized realized variance over (t, t + horizon*1h].

    Uses the `horizon` returns stamped t .. t+(horizon-1)h. Divides by the
    usable count, not by `horizon` (SPEC section 3.3).
    """
    i0 = series.index_of(t)
    i1 = i0 + horizon
    if i0 < 0 or i1 > len(series.r2_prefix) - 1:
        raise GapError(f"window [{i0}, {i1}) outside series of "
                       f"{len(series.r2_prefix) - 1} returns")
    count = series.cnt_prefix[i1] - series.cnt_prefix[i0]
    if count == 0:
        raise GapError(f"no usable returns in window at {t}")
    total = series.r2_prefix[i1] - series.r2_prefix[i0]
    return (total / count) * ANNUALIZATION_HOURS


def iv_var(dvol_open: float) -> float:
    """Annualized implied variance from a DVOL vol-point quote."""
    return (dvol_open / 100.0) ** 2


def spread_series(dvol: list[tuple[int, float]],
                  series: ReturnSeries) -> list[tuple[int, float]]:
    """[(t, iv_var(t) - rv_var(t))] over every DVOL point supplied."""
    return [(t, iv_var(v) - rv_var(series, t)) for t, v in dvol]


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean of empty series")
    return sum(values) / len(values)


def block_bootstrap_mean_ci(values: list[float], block_len: int = BLOCK_LEN,
                            n_resamples: int = N_RESAMPLES,
                            seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """(p2.5, p97.5) of the mean over moving-block bootstrap resamples.

    Block length matches the 30-day overlap horizon, so the resample preserves
    the autocorrelation the overlap induces (SPEC section 4.3). Never compute a
    naive SE on the overlapping series -- it is wrong by roughly sqrt(60).
    """
    n = len(values)
    if n <= block_len:
        raise ValueError(f"series of {n} shorter than bootstrap block {block_len}")
    rng = random.Random(seed)
    n_blocks = -(-n // block_len)  # ceil
    means: list[float] = []
    for _ in range(n_resamples):
        sample = fixed_block_count_resample(rng, values, block_len, n_blocks)
        means.append(sum(sample) / len(sample))
    return percentile(means, 2.5), percentile(means, 97.5)


def disjoint_spreads(spread: list[tuple[int, float]],
                     stride_ms: int = DISJOINT_STRIDE_MS) -> list[float]:
    """Non-overlapping windows at phase 0: the value at t0, t0+30d, t0+60d, …"""
    if not spread:
        raise ValueError("disjoint_spreads of empty series")
    by_ts = dict(spread)
    t0 = spread[0][0]
    t_last = spread[-1][0]
    out: list[float] = []
    t = t0
    while t <= t_last:
        if t in by_ts:
            out.append(by_ts[t])
        t += stride_ms
    return out


def plain_mean_ci(values: list[float]) -> tuple[float, float]:
    """Normal-approximation 95% CI on the mean. For the DISJOINT series only."""
    n = len(values)
    if n < 2:
        raise ValueError(f"need >= 2 values, got {n}")
    m = mean(values)
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    half = 1.96 * math.sqrt(var / n)
    return m - half, m + half


def year_buckets(spread: list[tuple[int, float]]) -> dict[int, list[float]]:
    """Calendar-year buckets keyed by the year of t, never of t + 30d
    (SPEC section 6 clause 3)."""
    out: dict[int, list[float]] = {}
    for t, v in spread:
        year = dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).year
        out.setdefault(year, []).append(v)
    return out


def sigma_path(dvol: list[tuple[int, float]], first_ret_ts: int,
               n: int) -> list[float]:
    """Hourly instantaneous vol implied by DVOL, held piecewise-constant across
    each 12h bar (SPEC section 5.2). sigma(h) = dvol_open(t(h))/100/sqrt(8760),
    t(h) = the most recent DVOL bar stamped at or before h. No interpolation.
    """
    if not dvol:
        raise GapError("sigma_path: empty DVOL series")
    if first_ret_ts < dvol[0][0]:
        raise GapError(f"sigma_path: {first_ret_ts} precedes first DVOL bar "
                       f"{dvol[0][0]}")
    out: list[float] = []
    idx = 0
    for i in range(n):
        h = first_ret_ts + i * HOUR_MS
        while idx + 1 < len(dvol) and dvol[idx + 1][0] <= h:
            idx += 1
        out.append(dvol[idx][1] / 100.0 / math.sqrt(ANNUALIZATION_HOURS))
    return out


def draw_gaussian(rng: random.Random) -> float:
    """Unit-variance normal innovation."""
    return rng.gauss(0.0, 1.0)


def draw_student_t(rng: random.Random, df: int = T_DF) -> float:
    """Student-t(df) innovation rescaled to UNIT VARIANCE.

    t(df) has variance df/(df-2) -- 2.0 at df=4 -- so divide by sqrt of that.
    df is a pre-committed convention (SPEC section 5.3): not estimated from the
    data, not swept.
    """
    if df <= 2:
        raise ValueError(f"df must exceed 2 for finite variance, got {df}")
    # t = Z / sqrt(V/df), V ~ chi-square(df) = sum of df squared normals.
    z = rng.gauss(0.0, 1.0)
    v = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(df))
    raw = z / math.sqrt(v / df)
    return raw / math.sqrt(df / (df - 2.0))


def synthetic_returns(sigmas: list[float], rng: random.Random, draw) -> list[float]:
    """Hourly log returns with true instantaneous vol `sigmas`, iid given sigma."""
    return [s * draw(rng) for s in sigmas]


def null_mean_spread(dvol: list[tuple[int, float]], first_ret_ts: int,
                     usable: list[bool], sigmas: list[float], seed: int,
                     draw) -> float:
    """mean_spread from one synthetic path, measured against the REAL DVOL
    series through the identical pipeline (SPEC section 5.2 step 4)."""
    rng = random.Random(seed)
    returns = synthetic_returns(sigmas, rng, draw)
    series = build_return_series_from_returns(returns, first_ret_ts, usable)
    return mean([v for _, v in spread_series(dvol, series)])


def null_distribution(dvol: list[tuple[int, float]], first_ret_ts: int,
                      usable: list[bool], sigmas: list[float], base_seed: int,
                      draw, n_seeds: int = N_NULL_SEEDS) -> list[float]:
    """The distribution of mean_spread in a world where the premium is exactly
    zero by construction."""
    return [null_mean_spread(dvol, first_ret_ts, usable, sigmas, base_seed + i, draw)
            for i in range(n_seeds)]


def vol_point_spreads(dvol: list[tuple[int, float]],
                      series: ReturnSeries) -> list[tuple[int, float]]:
    """DESCRIPTIVE ONLY (SPEC section 4.4): dvol_open(t) - 100*sqrt(rv_var(t)).
    Jensen-biased relative to the variance claim; never part of a threshold."""
    return [(t, v - 100.0 * math.sqrt(rv_var(series, t))) for t, v in dvol]


def _utc_date(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M")


def tail_windows(spread: list[tuple[int, float]], series: ReturnSeries,
                 k: int = 5) -> list[dict]:
    """The k windows with the highest realized variance, and the spread in each.

    DESCRIPTIVE (SPEC section 7 Q5). A short-vol premium's entire risk is that
    it is collected in calm and repaid in spikes. Deliberately NOT part of the
    section 6 threshold: making it one would be designing an exit rule.
    """
    rows = [{"t": t, "date_utc": _utc_date(t), "rv_var": rv_var(series, t),
             "spread": s} for t, s in spread]
    rows.sort(key=lambda r: r["rv_var"], reverse=True)
    return rows[:k]


def evaluate_threshold(results: dict) -> dict:
    """The section 6 continuation threshold. All three clauses required.

    This decides whether a Stage-1 spec gets written -- NOT whether anything
    trades. It is not a verdict (SPEC section 0.2).
    """
    m = results["mean_spread"]
    null_clears = (m > results["null_gaussian"]["p97_5"]
                   and m > results["null_student_t"]["p97_5"])
    interval_clears = (results["bootstrap_ci"][0] > 0.0
                       and results["disjoint_ci"][0] > 0.0)
    positive = sum(1 for b in results["year_buckets"].values() if b["mean"] > 0.0)
    stability_clears = positive >= 5
    return {"null_clears": null_clears,
            "interval_clears": interval_clears,
            "stability_clears": stability_clears,
            "buckets_positive": positive,
            "continue_recommended": bool(null_clears and interval_clears
                                         and stability_clears)}


def assemble_results(dvol: list[tuple[int, float]], series: ReturnSeries,
                     n_null_seeds: int = N_NULL_SEEDS) -> dict:
    """Every frozen question (SPEC section 7) in one pass."""
    spread = spread_series(dvol, series)
    values = [v for _, v in spread]
    m = mean(values)
    disjoint = disjoint_spreads(spread)
    buckets = {year: {"mean": mean(vs), "n": len(vs)}
               for year, vs in sorted(year_buckets(spread).items())}

    n_ret = len(series.r2_prefix) - 1
    sigmas = sigma_path(dvol, series.first_ts, n_ret)
    usable = [series.cnt_prefix[i + 1] - series.cnt_prefix[i] == 1
              for i in range(n_ret)]

    nulls = {}
    for name, base_seed, draw in (("null_gaussian", NULL_SEED_GAUSS, draw_gaussian),
                                  ("null_student_t", NULL_SEED_T, draw_student_t)):
        dist = null_distribution(dvol, series.first_ts, usable, sigmas,
                                 base_seed, draw, n_seeds=n_null_seeds)
        nulls[name] = {"n_seeds": len(dist), "mean": mean(dist),
                       "p2_5": percentile(dist, 2.5),
                       "p50": percentile(dist, 50.0),
                       "p97_5": percentile(dist, 97.5)}

    results = {
        "window": {"start_ms": dvol[0][0], "end_ms": dvol[-1][0],
                   "start_utc": _utc_date(dvol[0][0]),
                   "end_utc": _utc_date(dvol[-1][0]),
                   "n_dvol_bars": len(dvol), "n_returns": n_ret,
                   "n_excluded_returns": n_ret - series.cnt_prefix[-1]},
        "mean_spread": m,
        "median_spread": percentile(values, 50.0),
        "frac_positive": sum(1 for v in values if v > 0.0) / len(values),
        "bootstrap_ci": block_bootstrap_mean_ci(values),
        "disjoint_n": len(disjoint),
        "disjoint_mean": mean(disjoint),
        "disjoint_ci": plain_mean_ci(disjoint),
        "year_buckets": buckets,
        "tail_windows": tail_windows(spread, series),
        "vol_point_mean": mean([v for _, v in vol_point_spreads(dvol, series)]),
    }
    results.update(nulls)
    results["bias_corrected_spread"] = m - nulls["null_gaussian"]["mean"]
    results["threshold"] = evaluate_threshold(results)
    return results


def render_results_md(results: dict, meta: dict) -> str:
    """RESULTS.md. Descriptive throughout: no verdict, no recommendation to
    trade (SPEC section 0.1)."""
    out: list[str] = []
    add = out.append
    w = results["window"]
    add("# vrp_measure — BTC Variance Risk Premium (frozen measurement run)")
    add("")
    add("Measurement lane: descriptive accounting over pinned data. Nothing is")
    add("predicted. There is no verdict here and no trading rule. See")
    add("`experiments/vrp_measure/SPEC.md`.")
    add("")
    add(f"- commit: `{meta.get('commit', '')}`")
    for name, info in sorted(meta.get("inputs_sha256", {}).items()):
        add(f"- {name}: `{info['path']}` sha256 `{info['sha256']}`")
    add("")
    add("## Q1 — data integrity")
    add("")
    add(f"- window: {w['start_utc']} → {w['end_utc']} UTC")
    add(f"- DVOL bars: {w['n_dvol_bars']}")
    add(f"- hourly returns: {w['n_returns']}")
    add(f"- returns excluded at splice boundaries: {w['n_excluded_returns']}")
    add("")
    add("## Q2 — the spread, full window (annualized variance)")
    add("")
    add(f"- mean (overlapping, primary): {results['mean_spread']:+.6f}")
    add(f"- median: {results['median_spread']:+.6f}")
    add(f"- fraction of windows positive: {results['frac_positive']:.4f}")
    add(f"- block-bootstrap 95% CI: [{results['bootstrap_ci'][0]:+.6f}, "
        f"{results['bootstrap_ci'][1]:+.6f}]")
    add(f"- disjoint cross-check (n={results['disjoint_n']}): "
        f"mean {results['disjoint_mean']:+.6f}, CI "
        f"[{results['disjoint_ci'][0]:+.6f}, {results['disjoint_ci'][1]:+.6f}]")
    add("")
    add("## Q3 — year by year")
    add("")
    add("| year | mean spread | n |")
    add("|---|---|---|")
    for year, b in results["year_buckets"].items():
        add(f"| {year} | {b['mean']:+.6f} | {b['n']} |")
    add("")
    add("## Q4 — null calibration (the gate)")
    add("")
    add("| null | seeds | mean | p2.5 | p50 | p97.5 |")
    add("|---|---|---|---|---|---|")
    for name in ("null_gaussian", "null_student_t"):
        n = results[name]
        add(f"| {name} | {n['n_seeds']} | {n['mean']:+.6f} | {n['p2_5']:+.6f} "
            f"| {n['p50']:+.6f} | {n['p97_5']:+.6f} |")
    add("")
    add(f"- real mean − gaussian null mean: {results['bias_corrected_spread']:+.6f}")
    t = results["threshold"]
    add(f"- clause 1 (above both null p97.5): {t['null_clears']}")
    add(f"- clause 2 (both CIs above zero): {t['interval_clears']}")
    add(f"- clause 3 (≥5 of 6 buckets positive): {t['stability_clears']} "
        f"({t['buckets_positive']} of {len(results['year_buckets'])})")
    add("")
    add(f"**Continuation (SPEC §6): {t['continue_recommended']}** — this decides")
    add("only whether a Stage-1 spec is written. It is not a verdict.")
    add("")
    add("## Q5 — tail behavior (descriptive, not part of §6)")
    add("")
    add("| window start (UTC) | realized variance | spread |")
    add("|---|---|---|")
    for row in results["tail_windows"]:
        add(f"| {row['date_utc']} | {row['rv_var']:.6f} | {row['spread']:+.6f} |")
    add("")
    add("## Q6 — vol-point spread (descriptive secondary)")
    add("")
    add(f"- mean DVOL − realized vol: {results['vol_point_mean']:+.4f} vol points")
    add("")
    add("Jensen caveat: E[σ]² ≠ E[σ²], so this is biased relative to the")
    add("variance-space claim in Q2. It is reported because vol points are how")
    add("volatility is read, and is not part of any threshold.")
    add("")
    return "\n".join(out)
