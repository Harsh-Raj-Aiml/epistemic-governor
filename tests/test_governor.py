"""Phase 1 + Phase 2 tests for the Governor core and impossibility certificate."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from governor.core import Governor


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------


def test_passing_command_is_not_impossible():
    g = Governor("task: add two numbers")
    cid = g.checkpoint("initial")
    assert cid
    assert g.checkpoints == [(cid, "initial")]

    record = g.fork_and_test("run python", "python", ["-c", "print(1 + 1)"])
    assert record["exit_code"] == 0
    assert g._indicates_impossibility(record) is False
    assert g.impossibility_forks == []
    assert g.is_impossible() is False


def test_module_not_found_is_impossible_signal():
    g = Governor("task: import a package")
    g.checkpoint("initial")

    record = g.fork_and_test(
        "import missing pkg", "python", ["-c", "import nonexistent_pkg_alpha"]
    )
    assert record["exit_code"] != 0
    assert "ModuleNotFoundError" in record["stderr"]
    assert g._indicates_impossibility(record) is True
    assert len(g.impossibility_forks) == 1


def test_three_same_signature_hypotheses_means_impossible():
    g = Governor("task: repair missing dependency")
    g.checkpoint("initial")

    for pkg in ["nonexistent_pkg_alpha", "nonexistent_pkg_beta", "nonexistent_pkg_gamma"]:
        g.fork_and_test(f"import {pkg}", "python", ["-c", f"import {pkg}"])

    assert len(g.impossibility_forks) == 3
    assert g.is_impossible() is True
    assert g.proven_impossible is False  # not yet certified


def test_three_different_signatures_means_not_impossible():
    g = Governor("task: mixed failures")
    g.checkpoint("initial")

    g.fork_and_test("import missing pkg", "python", ["-c", "import nonexistent_pkg_alpha"])
    g.fork_and_test(
        "import broken version",
        "python",
        ["-c", "import sys; sys.stderr.write('ImportError: version mismatch\\n'); sys.exit(1)"],
    )
    g.fork_and_test(
        "hit 404 endpoint",
        "python",
        ["-c", "import sys; sys.stderr.write('404 Not Found\\n'); sys.exit(1)"],
    )

    assert len(g.impossibility_forks) == 3
    assert g.is_impossible() is False


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------


def test_certificate_build_and_verify():
    g = Governor("task: repair impossible thing")
    g.checkpoint("initial")
    for pkg in ["nonexistent_pkg_alpha", "nonexistent_pkg_beta", "nonexistent_pkg_gamma"]:
        g.fork_and_test(f"import {pkg}", "python", ["-c", f"import {pkg}"])

    assert g.is_impossible() is True
    cert = g.produce_certificate()

    from governor.certificate import verify

    assert verify(cert) is True
    assert cert["verdict"] == "IMPOSSIBLE"
    assert cert["blocker_signature"] == "ModuleNotFoundError"
    assert cert["task_spec"] == "task: repair impossible thing"
    assert len(cert["impossibility_forks"]) == 3
    assert "certificate_hash" in cert
    assert len(cert["certificate_hash"]) == 64


def test_certificate_verify_detects_mutation():
    g = Governor("task: x")
    g.checkpoint("initial")
    for pkg in ["nonexistent_pkg_alpha", "nonexistent_pkg_beta", "nonexistent_pkg_gamma"]:
        g.fork_and_test(f"import {pkg}", "python", ["-c", f"import {pkg}"])
    cert = g.produce_certificate()

    mutated = dict(cert)
    mutated["impossibility_forks"] = [
        dict(f, stderr="tampered stderr") for f in cert["impossibility_forks"]
    ]
    from governor.certificate import verify

    assert verify(mutated) is False
