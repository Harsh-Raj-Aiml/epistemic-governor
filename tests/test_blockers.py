"""Tests for the blockers registry."""

from . import blockers


def test_all_blockers_have_signature():
    for name in blockers.BLOCKER_NAMES:
        assert name in blockers.BLOCKER_SIGNATURES, f"missing signature for {name}"
        sig = blockers.BLOCKER_SIGNATURES[name]
        assert sig in blockers.HYPOTHESIS_COMMANDS, f"no hypotheses for signature {sig}"
        assert len(blockers.HYPOTHESIS_COMMANDS[sig]) == 3


def test_blocker_returns_tuple():
    task, setup, marker = blockers.missing_dependency()
    assert isinstance(task, str) and task
    assert isinstance(setup, str)
    assert isinstance(marker, str) and marker
