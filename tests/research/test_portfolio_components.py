from moonface.research.portfolio.components import center_components

EXPECTED_LABELS = {
    "1h:roc_sign:period=24",
    "1h:atr_channel_break:k=1.5",
    "1h:trend_pullback:pull_atr=1.0",
    "1h:vol_expansion:mult=2.0",
    "1h:vol_regime:window=48",
    "4h:ma_cross:slow=100",
    "4h:donchian_break:n=55",
    "4h:atr_channel_break:k=1.5",
    "4h:vol_regime:window=48",
}


def test_center_components_count_and_labels():
    cells = center_components()
    assert len(cells) == 9
    assert {c.label for c in cells} == EXPECTED_LABELS


def test_center_components_timeframe_split():
    cells = center_components()
    tfs = {}
    for c in cells:
        tfs[c.timeframe] = tfs.get(c.timeframe, 0) + 1
    assert tfs == {"1h": 5, "4h": 4}


def test_center_components_are_median_swept():
    from moonface.research.system_cells import system_cells_for
    cells = center_components()
    # For each (tf, family) the chosen swept equals the median of the 3 swept values.
    for c in cells:
        group = sorted(x.swept for x in system_cells_for(c.timeframe)
                       if x.family == c.family)
        assert c.swept == group[len(group) // 2]
