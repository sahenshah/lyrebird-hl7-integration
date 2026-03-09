"""Test 4: Recovery after downstream returns (AE then AA)."""
import subprocess
import sys
import time
import socket
from pathlib import Path


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


def _start_downstream_9000(project_root: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            "uvicorn",
            "app.stub_api:app",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--ssl-keyfile", "certs/stub.key",
            "--ssl-certfile", "certs/stub.crt",
            "--log-level", "warning",
        ],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _is_open("127.0.0.1", 9000):
            return proc
        time.sleep(0.2)
    proc.terminate()
    raise AssertionError("Downstream failed to start on 9000")


def test_recovery_and_retry(services, downstream_api, project_root, tmp_path):
    control_id = "RECOVERY-001"
    msg = _make_message_with_control_id(project_root, tmp_path, control_id)

    # 1) Downstream down -> expect AE
    _kill_downstream_9000()
    for _ in range(30):
        if not _is_open("127.0.0.1", 9000):
            break
        time.sleep(0.2)
    assert not _is_open("127.0.0.1", 9000), "Downstream should be down before first send"

    out1 = _send(project_root, msg)
    assert "MSA|AE" in out1, f"Expected AE when downstream is down. Output:\n{out1}"

    # 2) Downstream up -> resend same message -> expect AA
    proc = _start_downstream_9000(project_root)
    try:
        out2 = _send(project_root, msg)
        assert "MSA|AA" in out2, f"Expected AA after downstream recovery. Output:\n{out2}"
    finally:
        # leave cleanup to fixture lifecycle if preferred; this is defensive
        if proc.poll() is None:
            proc.terminate()