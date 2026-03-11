"""Test 3: New message with downstream down."""
import json
import subprocess
import sys
import uuid
from pathlib import Path
import socket
import pytest
import time


def _send(project_root: Path, msg: Path) -> str:
    p = subprocess.run(
        [sys.executable, "-m", "app.sender", "--file", str(msg)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")


def _make_message_with_control_id(project_root: Path, tmp_path: Path, control_id: str) -> Path:
    src = project_root / "examples" / "sample_adt_a01.hl7"
    lines = src.read_text().splitlines()
    msh = lines[0].split("|")
    msh[9] = control_id  # MSH-10
    lines[0] = "|".join(msh)
    out = tmp_path / f"{control_id}.hl7"
    out.write_text("\n".join(lines) + "\n")
    return out


def _is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _kill_downstream_9000() -> None:
    subprocess.run(
        ["bash", "-lc", "pkill -f 'uvicorn app.stub_api:app.*--port 9000'"],
        check=False,
        capture_output=True,
        text=True,
    )

def _is_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
    

@pytest.fixture
def send_prereqs_ready(services, downstream_api):
    if not _is_reachable("127.0.0.1", 2575):
        pytest.skip("Skipping send test: listener on 2575 is not reachable")


def test_new_message_downstream_down(services, downstream_api, project_root, tmp_path):
    _kill_downstream_9000()

    # hard check: downstream must be down before sending
    for _ in range(20):
        if not _is_open("127.0.0.1", 9000):
            break
        time.sleep(0.2)
    assert not _is_open("127.0.0.1", 9000), "Downstream still reachable on 9000"

    control_id = "FAIL-d1fbaaf6"
    msg = _make_message_with_control_id(project_root, tmp_path, control_id)

    output = _send(project_root, msg)
    assert "MSA|AE" in output, f"Expected AE when downstream is down. Output:\n{output}"

    audit = project_root / "logs" / "publisher_audit.jsonl"
    entries = []
    if audit.exists():
        with open(audit) as f:
            entries = [json.loads(line) for line in f if line.strip()]

    cid_entries = [e for e in entries if e.get("message_control_id") == control_id]
    assert cid_entries, f"No audit entries for control_id={control_id}"
    assert any(e.get("status") == "nack" for e in cid_entries), f"Expected status='nack', got: {cid_entries}"