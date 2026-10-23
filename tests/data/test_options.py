"""Tests for the Deribit DVOL fetcher.

The fake here mimics Deribit's ACTUAL behavior: get_volatility_index_data
returns the MOST RECENT `page_size` points inside [start, end], not the
earliest. The previous version of this test returned pages ascending from
`start`, which encoded the same wrong model as the bug it was meant to catch
(SPEC vrp_measure section 2.1).
"""
from __future__ import annotations

import urllib.parse

from moonface.data.options import (
    DvolPoint,
    fetch_dvol,
    parse_dvol_payload,
)

RES = 43200
RES_MS = RES * 1000


class FakeDeribit:
    """Serves from a fixed universe of 12h bars, most-recent-N first."""

    def __init__(self, first_ts: int, n_bars: int, page_size: int = 1000):
        self.bars = [
            [first_ts + i * RES_MS, float(i), float(i), float(i), float(i)]
            for i in range(n_bars)
        ]
        self.page_size = page_size
        self.calls = 0

    def __call__(self, url: str) -> dict:
        self.calls += 1
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        start = int(q["start_timestamp"][0])
        end = int(q["end_timestamp"][0])
        window = [b for b in self.bars if start <= b[0] <= end]
        return {"result": {"data": window[-self.page_size:]}}


def test_parse_payload():
    payload = {"result": {"data": [
        [1739232000000, 52.4, 54.67, 52.08, 53.23],
        [1739275200000, 53.23, 54.0, 52.9, 53.8],
    ]}}
    pts = parse_dvol_payload(payload)
    assert pts[0] == DvolPoint(1739232000000, 52.4, 54.67, 52.08, 53.23)
    assert len(pts) == 2


def test_fetch_walks_back_past_one_page(tmp_path):
    """The bug: a single page is the LAST 1000 bars, so forward paging stops
    there. 2500 bars must require 3 backward pages and return all of them."""
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=2500, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 2500 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    assert len(pts) == 2500, f"got {len(pts)} bars (forward-paging bug returns 1000)"
    assert [p.ts_ms for p in pts] == sorted(p.ts_ms for p in pts)
    assert pts[0].ts_ms == 1_000_000_000_000
    assert fake.calls >= 3


def test_fetch_backward_pages_are_contiguous(tmp_path):
    """With cursor stepping back a full resolution per page, consecutive
    backward pages never overlap in ts -- this proves CONTIGUITY, not dedup.
    (Originally named test_fetch_dedups_overlapping_pages; renamed because a
    task review on 2026-07-17 executed this exact scenario and found the two
    pages share zero timestamps: page 1 returns bars[500:1500], page 2
    returns bars[0:500]. See test_fetch_dedups_repeated_timestamp_across_calls
    below for the actual dedup-path coverage.)"""
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=1500, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 1500 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    ts = [p.ts_ms for p in pts]
    assert len(ts) == len(set(ts)) == 1500


def test_fetch_dedups_repeated_timestamp_across_calls(tmp_path):
    """Hand-crafted fake (not FakeDeribit) where page 2 re-serves page 1's
    oldest point plus two genuinely new ones -- FakeDeribit's exact backward
    stepping never produces this on its own (see the test above), but a real
    API response isn't guaranteed to align to resolution_ms boundaries.
    Proves `seen`/`fresh` dedups the repeat rather than double-counting it."""
    base = 1_000_000_000_000
    page1 = [[base + 2 * RES_MS, 2.0, 2.0, 2.0, 2.0],
             [base + 3 * RES_MS, 3.0, 3.0, 3.0, 3.0],
             [base + 4 * RES_MS, 4.0, 4.0, 4.0, 4.0]]
    page2 = [[base, 0.0, 0.0, 0.0, 0.0],
             [base + RES_MS, 1.0, 1.0, 1.0, 1.0],
             [base + 2 * RES_MS, 2.0, 2.0, 2.0, 2.0]]  # repeats page1[0]
    pages = [page1, page2]
    calls = {"n": 0}

    def fake_get(url):
        p = pages[min(calls["n"], len(pages) - 1)]
        calls["n"] += 1
        return {"result": {"data": p}}

    pts = fetch_dvol("BTC", base, base + 4 * RES_MS, str(tmp_path),
                     resolution=RES, get_json=fake_get)
    assert len(pts) == 5, "repeated point must be deduped, not double-counted"
    assert [p.ts_ms for p in pts] == [base + i * RES_MS for i in range(5)]
    assert calls["n"] == 2


def test_fetch_single_page_terminates(tmp_path):
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=10, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    assert len(pts) == 10
    # One call only: the single page's earliest bar equals start_ms, so
    # cursor - resolution_ms steps below start_ms and the loop's own
    # boundary check proves exhaustion without an extra empty-page round
    # trip. (Originally asserted calls == 2; a task review on 2026-07-17
    # executed this exact code and found the boundary check always fires
    # first, making 2 calls unreachable for a genuine single-page range.)
    assert fake.calls == 1


def test_fetch_uses_cache_and_skips_network(tmp_path):
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=10)
    fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
               str(tmp_path), resolution=RES, get_json=fake)
    before = fake.calls

    def boom(url):
        raise AssertionError("network hit despite cache")

    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=boom)
    assert len(pts) == 10
    assert fake.calls == before
