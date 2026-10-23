import json

from moonface.research.breadth_internal.ensemble import (
    load_survivors,
    net_vote_state,
)


def test_net_vote_sign_with_ties_flat():
    a = [(0, "LONG"), (1, "LONG"), (2, "SHORT")]
    b = [(0, "LONG"), (1, "SHORT"), (2, "SHORT")]
    c = [(0, "FLAT"), (1, "FLAT"), (2, "LONG")]
    # ts0: +1+1+0=+2 -> LONG ; ts1: +1-1+0=0 -> FLAT ; ts2: -1-1+1=-1 -> SHORT
    assert net_vote_state([a, b, c]) == [(0, "LONG"), (1, "FLAT"), (2, "SHORT")]


def test_net_vote_only_shared_timestamps():
    a = [(0, "LONG"), (1, "LONG")]
    b = [(1, "LONG"), (2, "LONG")]
    assert net_vote_state([a, b]) == [(1, "LONG")]  # only ts=1 is shared


def test_load_survivors_filters_forward_candidates(tmp_path):
    result = {
        "windows": {"sealed": [100, 999]},
        "rows": [
            {"verdict": "forward_candidate",
             "spec": {"key": "net_new_highs", "builder": "net_new_highs",
                      "params": {"n": 20}, "exit_name": "atr_trail",
                      "exit_params": {}, "h": 48}},
            {"verdict": "negative",
             "spec": {"key": "dud", "builder": "x", "params": {},
                      "exit_name": "atr_trail", "exit_params": {}, "h": 48}},
        ],
    }
    p = tmp_path / "RESULT.json"
    p.write_text(json.dumps(result))
    survivors = load_survivors([str(p)])
    assert len(survivors) == 1
    assert survivors[0]["spec"]["key"] == "net_new_highs"
    assert survivors[0]["sealed_end"] == 999
