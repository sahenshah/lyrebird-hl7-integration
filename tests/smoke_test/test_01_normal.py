"""Test 1: Normal operation - all services up."""
import pytest
import requests
import socket
import sys
import subprocess


def _is_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def test_backend_api_not_reachable_from_host(services, downstream_api):
    # Backend should NOT be reachable from host if not published
    try:
        requests.get("http://127.0.0.1:8000/api/v1/messages", timeout=2)
        assert False, "Backend unexpectedly reachable on host port 8000"
    except requests.exceptions.RequestException:
        pass


@pytest.fixture
def send_prereqs_ready(services, downstream_api):
    if not _is_reachable("127.0.0.1", 2575):
        pytest.skip("Skipping send test: listener on 2575 is not reachable")
    if not _is_reachable("127.0.0.1", 9000):
        pytest.skip("Skipping send test: downstream API on 9000 is not reachable")


def test_send_sample_adt_a01(services, downstream_api, send_prereqs_ready, project_root):
    msg_file = project_root / "examples" / "sample_adt_a01.hl7"

    result = subprocess.run(
        [sys.executable, "-m", "app.sender", "--file", str(msg_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    assert "MSA|AA" in output, f"Expected AA ACK, got:\n{output}"