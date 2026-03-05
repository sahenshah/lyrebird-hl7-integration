import pytest
import subprocess
import time
import requests
import os
import signal
import socket
import sys
from urllib.parse import urlparse
from app.core.config import API_URL

parsed_url = urlparse(API_URL)
api_scheme = parsed_url.scheme
api_host = parsed_url.hostname or "127.0.0.1"
api_port = parsed_url.port or (443 if api_scheme == "https" else 80)
api_base = f"{api_scheme}://{api_host}:{api_port}"

@pytest.fixture(scope="session", autouse=True)
def start_api():
    """Start FastAPI uvicorn server in a subprocess for the test session."""
    uvicorn_cmd = [
        "uvicorn",
        "app.api:app",
        "--host", api_host,
        "--port", str(api_port),
        "--log-config", "logging_config.json",
    ]

    if sys.platform == "win32":
        proc = subprocess.Popen(
            uvicorn_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        proc = subprocess.Popen(
            uvicorn_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )

    # Wait until API is ready
    timeout = 10  # seconds
    start = time.time()
    while True:
        try:
            requests.get(f"{api_base}/docs")
            break
        except requests.ConnectionError:
            if time.time() - start > timeout:
                proc.terminate()
                raise RuntimeError("API did not start within timeout")
            time.sleep(0.2)

    yield  # run the tests

    # Teardown: kill the uvicorn subprocess
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait()

def wait_for_port(host, port, timeout=10):
    """Wait until a TCP port is open."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, int(port)), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for {host}:{port}")

@pytest.fixture(autouse=True)
def start_listener():
    """Start a fresh listener in background before each test, and stop after."""
    try:
        proc = subprocess.Popen(["python3", "-m", "app.listener"])
    except FileNotFoundError:
        proc = subprocess.Popen(["python", "-m", "app.listener"])
    wait_for_port("127.0.0.1", 2575, timeout=10)
    yield
    proc.terminate()
    proc.wait()
