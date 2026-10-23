"""Regime->mechanism matrix: one mechanism per cell, empty cells allowed."""
from moonface.models.engine.v3.config_v3 import _FROZEN_MATRIX_TEXT
from moonface.models.engine.v3.matrix import (
    MECHANISMS,
    REGIME_MECHANISM,
    select_mechanism,
)
from moonface.models.engine.v3.regime import DirState, Regime, VolState


def test_every_cell_maps_and_names_are_known():
    assert len(REGIME_MECHANISM) == 9
    for name in REGIME_MECHANISM.values():
        assert name is None or name in MECHANISMS


def test_selection_matches_table():
    assert select_mechanism(
        Regime(DirState.TRENDING_UP, VolState.QUIET)) == "PULLBACK"
    assert select_mechanism(
        Regime(DirState.TRENDING_UP, VolState.NORMAL)) == "BREAKOUT"
    assert select_mechanism(
        Regime(DirState.RANGING, VolState.NORMAL)) == "REVERSION"
    assert select_mechanism(
        Regime(DirState.RANGING, VolState.HIGH)) is None
    assert select_mechanism(
        Regime(DirState.TRENDING_DOWN, VolState.HIGH)) == "BREAKOUT"


def test_registry_instances_expose_matching_names():
    for name, mech in MECHANISMS.items():
        assert mech.name == name


def test_table_agrees_with_hashed_matrix_text():
    rebuilt = ";".join(
        f"{d.value}|{v.value}="
        f"{REGIME_MECHANISM[(d, v)]}"
        for d in DirState for v in (VolState.QUIET, VolState.NORMAL, VolState.HIGH)
    )
    assert rebuilt == _FROZEN_MATRIX_TEXT
