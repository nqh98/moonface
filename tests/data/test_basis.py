from __future__ import annotations

import unittest

from moonface.data.series import align_basis
from moonface.core.models import Candle

_HOUR = 3_600_000


def _perp(ts: int, close: float) -> Candle:
    return Candle(ts, close, close, close, close, 1.0)


def _spot(ts: int, close: float) -> Candle:
    return Candle(ts, close, close, close, close, 1.0)


class AlignBasisTest(unittest.TestCase):
    def test_matched_timestamps(self) -> None:
        """When spot and perp share the same timestamps, basis is exact."""
        perp = [_perp(0, 102.0), _perp(_HOUR, 104.0), _perp(2 * _HOUR, 101.0)]
        spot = [_spot(0, 100.0), _spot(_HOUR, 100.0), _spot(2 * _HOUR, 100.0)]
        result = align_basis(perp, spot)
        # (102-100)/100 = 0.02, (104-100)/100 = 0.04, (101-100)/100 = 0.01
        self.assertEqual(result, [0.02, 0.04, 0.01])

    def test_gapped_sparse_spot(self) -> None:
        """Sparse spot carries the last close forward; never reads ahead."""
        perp = [
            _perp(0, 102.0),
            _perp(_HOUR, 103.0),
            _perp(2 * _HOUR, 104.0),
            _perp(3 * _HOUR, 105.0),
        ]
        # Only two spot bars: at t=0 and t=2h.
        spot = [_spot(0, 100.0), _spot(2 * _HOUR, 101.0)]
        result = align_basis(perp, spot)
        # t=0: (102-100)/100 = 0.02
        # t=1h: spot@0 still valid, (103-100)/100 = 0.03
        # t=2h: spot@2h applies, (104-101)/101 ≈ 0.02970...
        # t=3h: spot@2h still valid, (105-101)/101 ≈ 0.03960...
        self.assertAlmostEqual(result[0], 0.02)
        self.assertAlmostEqual(result[1], 0.03)
        self.assertAlmostEqual(result[2], 0.02970296, places=6)
        self.assertAlmostEqual(result[3], 0.03960396, places=6)

    def test_strict_no_lookahead(self) -> None:
        """Spot at exactly perp open time IS included; spot at open_time+1 is NOT."""
        perp = [_perp(100, 102.0), _perp(200, 103.0)]
        # Spot at t=100 matches perp[0]; spot at t=101 does NOT match perp[0].
        spot = [_spot(100, 100.0), _spot(101, 50.0), _spot(200, 101.0)]
        result = align_basis(perp, spot)
        # perp[0] (t=100): spot@100 included → (102-100)/100 = 0.02
        # perp[1] (t=200): spot@101 and spot@200 both <=200, last wins → (103-101)/101
        self.assertAlmostEqual(result[0], 0.02)
        self.assertAlmostEqual(result[1], (103.0 - 101.0) / 101.0)  # spot@200 last wins

    def test_no_lookahead_spot_after_perp_excluded(self) -> None:
        """A spot point strictly after perp open time must not be used."""
        perp = [_perp(100, 102.0)]
        spot = [_spot(101, 50.0)]  # spot AFTER perp open — must be excluded
        result = align_basis(perp, spot)
        self.assertIsNone(result[0])

    def test_pre_history_none(self) -> None:
        """Perp bars before the first spot point get None."""
        perp = [_perp(0, 102.0), _perp(_HOUR, 103.0), _perp(2 * _HOUR, 104.0)]
        spot = [_spot(2 * _HOUR, 100.0)]
        result = align_basis(perp, spot)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], (104.0 - 100.0) / 100.0)

    def test_empty_spot_list(self) -> None:
        """All perp bars get None when spot is empty."""
        perp = [_perp(0, 102.0), _perp(_HOUR, 103.0)]
        result = align_basis(perp, [])
        self.assertEqual(result, [None, None])

    def test_empty_perp_list(self) -> None:
        """Empty perp returns empty list regardless of spot."""
        spot = [_spot(0, 100.0)]
        result = align_basis([], spot)
        self.assertEqual(result, [])
