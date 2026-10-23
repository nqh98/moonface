from moonface.models.engine.moe.config_moe import MoeConfig, moe_hash


def test_defaults_and_hash_are_stable():
    cfg = MoeConfig()
    assert cfg.tau == 0.35
    assert cfg.q_confluence == 2
    assert cfg.m_per_weight == 50
    assert cfg.norm_mode == "rank"
    assert cfg.seed == 1729
    h1 = moe_hash(cfg)
    h2 = moe_hash(MoeConfig())
    assert h1 == h2 and len(h1) == 64


def test_hash_changes_with_tau():
    import dataclasses

    assert moe_hash(MoeConfig()) != moe_hash(dataclasses.replace(MoeConfig(), tau=0.5))
