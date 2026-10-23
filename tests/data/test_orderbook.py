# tests/test_bookdepth_data.py
import io
import tempfile
import unittest
import zipfile

from moonface.data.orderbook import fetch_bookdepth_history, parse_bookdepth_csv
from moonface.features.orderbook_features import imbalance_points

_CSV = """timestamp,percentage,depth,notional
2026-06-01 00:00:07,-5.00,9474.171,683676749.449
2026-06-01 00:00:07,-1.00,2265.754,166033819.786
2026-06-01 00:00:07,-0.20,354.437,26073796.282
2026-06-01 00:00:07,0.20,398.738,29403072.476
2026-06-01 00:00:07,1.00,1804.155,132267342.617
2026-06-01 00:00:07,5.00,9000.000,650000000.000
2026-06-01 00:00:37,-1.00,2000.000,150000000.000
2026-06-01 00:00:37,1.00,1000.000,75000000.000
"""

_TS0 = 1780272007000  # 2026-06-01 00:00:07 UTC
_TS1 = 1780272037000


class TestParse(unittest.TestCase):
    def test_keeps_only_the_one_percent_band(self):
        rows = parse_bookdepth_csv(_CSV)
        self.assertEqual(rows, [(_TS0, 166033819.786, 132267342.617),
                                (_TS1, 150000000.0, 75000000.0)])

    def test_snapshot_missing_one_side_is_dropped(self):
        csv_text = ("timestamp,percentage,depth,notional\n"
                    "2026-06-01 00:00:07,-1.00,1.0,100.0\n")
        self.assertEqual(parse_bookdepth_csv(csv_text), [])

    def test_imbalance_points(self):
        pts = imbalance_points([(_TS1, 150.0, 75.0), (_TS0, 0.0, 0.0)])
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0][0], _TS1)
        self.assertAlmostEqual(pts[0][1], (150 - 75) / (150 + 75))


def _zip_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("day.csv", text)
    return buf.getvalue()


class TestFetch(unittest.TestCase):
    def test_downloads_caches_and_skips_missing_days(self):
        day = 86_400_000
        start = (_TS0 // day) * day
        calls = []

        def get_bytes(url):
            calls.append(url)
            if "2026-06-02" in url:
                return None  # archive has no file for that day
            return _zip_bytes(_CSV)

        with tempfile.TemporaryDirectory() as tmp:
            rows = fetch_bookdepth_history("BTCUSDT", start, start + 2 * day,
                                           tmp, get_bytes=get_bytes)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(calls), 2)  # one per day, missing tolerated
            # second call fully served from cache
            again = fetch_bookdepth_history("BTCUSDT", start, start + day,
                                            tmp, get_bytes=get_bytes)
            self.assertEqual(len(calls), 2)
            self.assertEqual(again, rows)


if __name__ == "__main__":
    unittest.main()
