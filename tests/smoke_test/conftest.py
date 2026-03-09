from __future__ import annotations
from pathlib import Path
import socket
import subprocess
import sys
import time
import pytest

def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)

def _wait_tcp(host: str, port: int, timeout_s: int = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Timeout waiting for {host}:{port}")

@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

@pytest.fixture(scope="session")
def downstream_api(project_root: Path):
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.stub_api:app",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--ssl-keyfile",
            "certs/stub.key",
            "--ssl-certfile",
            "certs/stub.crt",
        ],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_tcp("127.0.0.1", 9000, timeout_s=30)
    try:
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

def _warmup_sender(project_root: Path, timeout_s: int = 45) -> None:
    """Send one warm-up message so first test send is not during startup race."""
    msg = project_root / "examples" / "sample_adt_a01.hl7"
    deadline = time.time() + timeout_s
    last_output = ""

    while time.time() < deadline:
        p = subprocess.run(
            [sys.executable, "-m", "app.sender", "--file", str(msg)],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        last_output = out
        if "MSA|AA" in out:
            return
        time.sleep(1)

    raise RuntimeError(f"Warm-up send did not succeed. Last output:\n{last_output}")

@pytest.fixture(scope="function")
def services(project_root: Path):
    subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], cwd=project_root, check=False, timeout=30)
    subprocess.run(["docker", "compose", "up", "--build", "-d"], cwd=project_root, check=True, timeout=180)
    _wait_tcp("127.0.0.1", 2575, timeout_s=60)
    time.sleep(1)
    try:
        yield
    finally:
        subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], cwd=project_root, check=False, timeout=30)

@pytest.fixture(scope="function")
def warmed_services(services, downstream_api, project_root: Path):
    _warmup_sender(project_root)
    return services

@pytest.fixture(autouse=True)
def clear_publisher_audit(services, project_root: Path):
    # clear after warm-up, before each test assertions
    p = project_root / "logs" / "publisher_audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    yield