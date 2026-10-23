import unittest

from moonface.research.microscope.regimes import (
    UNLABELED, label, label_series,
)


def _state(trend=0.0, vol=0.0, crowding=0.0, flow=0.0, rs=0.0):
    return {"trend": trend, "vol": vol, "crowding": crowding,
            "flow": flow, "relative_strength": rs}


class LabelTest(unittest.TestCase):
    def test_up_high_crowded_long(self):
        self.assertEqual(label(_state(trend=1.0, vol=1.0, crowding=1.5)),
                         "UP/HIGH/CROWDED_LONG")

    def test_down_low_crowded_short(self):
        self.assertEqual(label(_state(trend=-1.0, vol=-1.0, crowding=-1.5)),
                         "DOWN/LOW/CROWDED_SHORT")

    def test_range_mid_neutral(self):
        self.assertEqual(label(_state()), "RANGE/MID/NEUTRAL")

    def test_thresholds_are_exclusive(self):
        # exactly at threshold -> inner bucket
        self.assertEqual(label(_state(trend=0.5, vol=0.5, crowding=1.0)),
                         "RANGE/MID/NEUTRAL")

    def test_any_none_factor_is_unlabeled(self):
        s = _state(trend=1.0)
        s["flow"] = None
        self.assertEqual(label(s), UNLABELED)

    def test_label_series_shapes(self):
        states = {"XUSDT": [_state(), _state(trend=1.0, vol=1.0)]}
        out = label_series(states)
        self.assertEqual(out, {"XUSDT": ["RANGE/MID/NEUTRAL",
                                         "UP/HIGH/NEUTRAL"]})


if __name__ == "__main__":
    unittest.main()
