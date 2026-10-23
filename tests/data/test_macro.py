from moonface.data.macro import parse_fred_csv, MacroPoint

SAMPLE = "DATE,VIXCLS\n2024-01-02,13.20\n2024-01-03,.\n2024-01-04,14.04\n"

def test_parse_skips_missing_and_sets_utc_midnight():
    pts = parse_fred_csv(SAMPLE)
    assert pts == [
        MacroPoint(ts_ms=1704153600000, value=13.20),   # 2024-01-02 00:00Z
        MacroPoint(ts_ms=1704326400000, value=14.04),   # 2024-01-04 00:00Z
    ]

def test_parse_is_monotonic_ascending():
    pts = parse_fred_csv(SAMPLE)
    assert all(pts[i].ts_ms < pts[i + 1].ts_ms for i in range(len(pts) - 1))
