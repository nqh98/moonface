from moonface.research.exogenous.grid import PRECOMMITTED_STATES, N_TRIALS, StateDef


def test_states_are_frozen_and_signed():
    assert len(PRECOMMITTED_STATES) >= 4
    for s in PRECOMMITTED_STATES:
        assert isinstance(s, StateDef)
        assert s.op in (">", "<")
        assert s.sign in (1, -1)


def test_n_trials_at_least_state_count():
    assert N_TRIALS >= len(PRECOMMITTED_STATES)


def test_names_unique():
    names = [s.name for s in PRECOMMITTED_STATES]
    assert len(names) == len(set(names))
