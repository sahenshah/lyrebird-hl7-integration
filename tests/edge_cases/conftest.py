import pytest
import subprocess
import time
import requests
import os
import signal
import socket

API_HOST = "http://127.0.0.1:8080"

@pytest.fixture(scope="session", autouse=True)
def start_api():
    """Start FastAPI uvicorn server in a subprocess for the test session."""
    uvicorn_cmd = [
        "uvicorn",
        "app.api:app",
        "--port", "8080",
        "--log-config", "logging_config.json",
    ]

    proc = subprocess.Popen(
        uvicorn_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,  # allows killing the process group
    )

    # Wait until API is ready
    timeout = 10  # seconds
    start = time.time()
    while True:
        try:
            requests.get(f"{API_HOST}/docs")
            break
        except requests.ConnectionError:
            if time.time() - start > timeout:
                proc.terminate()
                raise RuntimeError("API did not start within timeout")
            time.sleep(0.2)

    yield  # run the tests

    # Teardown: kill the uvicorn subprocess
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait()

def wait_for_port(host, port, timeout=10):
    """Wait until a TCP port is open."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for {host}:{port}")

@pytest.fixture(autouse=True)
def start_listener():
    """Start a fresh listener in background before each test, and stop after."""
    proc = subprocess.Popen(["python3", "-m", "app.listener"])
    wait_for_port("127.0.0.1", 2575, timeout=10)
    yield
    proc.terminate()
    proc.wait()
