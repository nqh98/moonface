from moonface.research.breadth.grid import EXIT_NAME, EXIT_PARAMS, H, all_cells


def test_grid_has_nine_cells_three_families() -> None:
    cells = all_cells()
    assert len(cells) == 9
    fams = {c.family for c in cells}
    assert fams == {"pct_above_ma", "breadth_momentum", "breadth_thrust"}
    assert all(c.h == H and c.exit_name == EXIT_NAME for c in cells)


def test_axis_points_per_family() -> None:
    by_fam: dict[str, list[float]] = {}
    for c in all_cells():
        by_fam.setdefault(c.family, []).append(c.axis)
    assert sorted(by_fam["pct_above_ma"]) == [20, 50, 100]
    assert sorted(by_fam["breadth_momentum"]) == [6, 12, 24]
    assert sorted(by_fam["breadth_thrust"]) == [3, 6, 12]


def test_keys_unique() -> None:
    keys = [c.key for c in all_cells()]
    assert len(keys) == len(set(keys))


def test_exit_params_are_copied_per_cell() -> None:
    cells = all_cells()
    assert all(c.exit_params == EXIT_PARAMS for c in cells)
    assert all(c.exit_params is not EXIT_PARAMS for c in cells)
    assert len({id(c.exit_params) for c in cells}) == len(cells)
