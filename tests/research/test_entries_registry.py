from moonface.research.entries import known_families


def test_divergence_families_registered():
    fams = known_families()
    assert "price_oi_divergence" in fams
    assert "price_extension_short" in fams
