from moonface.research.price_oi_divergence_runner import (
    DIVERGENCE_DOMAIN, DIVERGENCE_START_MS, register)
from moonface.research.price_oi_divergence import divergence_specs
from moonface.kernel.store import Store


def test_register_is_idempotent_and_inserts_grid(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    now = DIVERGENCE_START_MS + 1_000_000_000
    register(store, now)
    register(store, now)
    d = store.domain(DIVERGENCE_DOMAIN, 1)
    assert d is not None
    assert d["config"]["runner"] == "price_oi_divergence"
    rows = store.rows(DIVERGENCE_DOMAIN, 1)
    assert len(rows) == len(divergence_specs()) == 4
