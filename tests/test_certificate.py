"""Phase 2 standalone certificate tests using a mock Governor."""

from unittest.mock import MagicMock

from governor.certificate import build, verify


def _mock_governor():
    g = MagicMock()
    g.task_spec = "task: mock impossible task"
    g.impossibility_forks = [
        {
            "hypothesis": "import pkg_a",
            "command": "python",
            "args": ["-c", "import nonexistent_pkg_a"],
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'nonexistent_pkg_a'",
            "exit_code": 1,
            "fork_id": "fork-1",
            "base_checkpoint": "ckpt-1",
        },
        {
            "hypothesis": "import pkg_b",
            "command": "python",
            "args": ["-c", "import nonexistent_pkg_b"],
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'nonexistent_pkg_b'",
            "exit_code": 1,
            "fork_id": "fork-2",
            "base_checkpoint": "ckpt-1",
        },
        {
            "hypothesis": "import pkg_c",
            "command": "python",
            "args": ["-c", "import nonexistent_pkg_c"],
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'nonexistent_pkg_c'",
            "exit_code": 1,
            "fork_id": "fork-3",
            "base_checkpoint": "ckpt-1",
        },
    ]
    g.checkpoint_ids.return_value = ["ckpt-1"]
    g._blocker_signature = lambda r: "ModuleNotFoundError"
    return g


def test_certificate_verify_true():
    cert = build(_mock_governor())
    assert verify(cert) is True
    assert cert["verdict"] == "IMPOSSIBLE"


def test_certificate_verify_false_on_mutation():
    cert = build(_mock_governor())
    mutated = dict(cert)
    mutated["impossibility_forks"] = [
        dict(f, stderr="tampered") for f in cert["impossibility_forks"]
    ]
    assert verify(mutated) is False
