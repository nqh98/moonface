from moonface.research.btcspec.select import TOP_K, island_ok, select


def _row(label, family, group, axis, total_r, pf):
    return {"label": label, "family": family, "group": group, "axis": axis,
            "metrics": {"total_r": total_r, "profit_factor": pf}}


def test_island_rejects_lone_spike():
    g = "g1"
    rows = [_row("a", "f", g, 1.0, 5.0, 2.0),   # spike
            _row("b", "f", g, 2.0, -3.0, 0.5),  # bad neighbour
            _row("c", "f", g, 3.0, -3.0, 0.5)]
    by_group = {g: rows}
    assert island_ok(rows[1], by_group) is True   # neighbour 'a' has PF>=1
    spike = rows[0]
    # 'a' only neighbour is 'b' (PF 0.5) -> lone spike
    assert island_ok(spike, by_group) is False


def test_select_takes_top_k_per_family_among_island_passers():
    g = "g1"
    rows = []
    for i, tr in enumerate([4.0, 3.0, 2.0, 1.0]):
        rows.append(_row(f"f1-{i}", "fam1", g, float(i), tr, 1.5))
    rows.append(_row("f2-0", "fam2", "g2", 0.0, 9.0, 1.5))
    rows.append(_row("f2-1", "fam2", "g2", 1.0, 8.0, 1.5))
    survivors = select(rows)
    fam1 = [s for s in survivors if s["family"] == "fam1"]
    assert len(fam1) == TOP_K            # capped at 3
    assert [s["label"] for s in fam1] == ["f1-0", "f1-1", "f1-2"]  # by total_r desc
    assert all(s["selection"]["passed"] for s in survivors)
