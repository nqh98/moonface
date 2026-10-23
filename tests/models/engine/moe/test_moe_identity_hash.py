import dataclasses

from moonface.models.engine.moe.config_moe import (MoeConfig, identity_hash,
                                                   moe_hash)

CONSTS = {"FUNDING_CAP": 0.01, "OI_LOOKBACK": 24}


def test_identity_hash_is_stable_and_64_hex():
    h1 = identity_hash(MoeConfig(), ["A", "B"], CONSTS)
    h2 = identity_hash(MoeConfig(), ["B", "A"], CONSTS)
    assert h1 == h2 and len(h1) == 64


def test_identity_hash_changes_with_expert_set():
    base = identity_hash(MoeConfig(), ["BREAKOUT", "PULLBACK", "REVERSION"],
                         CONSTS)
    more = identity_hash(
        MoeConfig(),
        ["BREAKOUT", "PULLBACK", "REVERSION", "FUNDING", "OI"],
        CONSTS,
    )
    assert base != more


def test_identity_hash_changes_with_config_and_constants():
    a = identity_hash(MoeConfig(), ["A"], CONSTS)
    b = identity_hash(dataclasses.replace(MoeConfig(), q_confluence=1), ["A"],
                      CONSTS)
    c = identity_hash(MoeConfig(), ["A"],
                      {"FUNDING_CAP": 0.02, "OI_LOOKBACK": 24})
    assert a != b and a != c
    assert a != moe_hash(MoeConfig())
