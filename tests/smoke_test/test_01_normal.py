"""Test 1: Normal operation - all services up."""
import pytest
import time
import requests
import socket
import sys
import subprocess

def test_listener_reachable_api_not_reachable(services, downstream_api):
    # Listener should be reachable from host (mapped port)
    with socket.create_connection(("127.0.0.1", 2575), timeout=2):
        pass

    # Separate downstream API session should be reachable on 9000
    with socket.create_connection(("127.0.0.1", 9000), timeout=2):
        pass

    # Backend should NOT be reachable from host if not published
    try:
        requests.get("http://127.0.0.1:8000/api/v1/messages", timeout=2)
        assert False, "Backend unexpectedly reachable on host port 8000"
    except requests.exceptions.RequestException:
        pass

def test_send_sample_adt_a02(services, downstream_api, project_root):
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