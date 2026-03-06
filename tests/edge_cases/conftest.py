import pytest
import subprocess
import time
import requests
import os
import signal
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse
from app.core.config import API_URL

parsed_url = urlparse(API_URL)
api_scheme = parsed_url.scheme
api_host = parsed_url.hostname or "127.0.0.1"
api_port = parsed_url.port or (443 if api_scheme == "https" else 80)
api_base = f"{api_scheme}://{api_host}:{api_port}"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CERT = os.getenv("TEST_SSL_CERTFILE", str(REPO_ROOT / "cert.pem"))
DEFAULT_KEY = os.getenv("TEST_SSL_KEYFILE", str(REPO_ROOT / "key.pem"))

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

    request_verify = True
    if api_scheme == "https":
        if not os.path.exists(DEFAULT_CERT) or not os.path.exists(DEFAULT_KEY):
            raise RuntimeError(
                f"HTTPS test mode requires cert/key. Missing cert={DEFAULT_CERT} or key={DEFAULT_KEY}"
            )
        uvicorn_cmd += ["--ssl-certfile", DEFAULT_CERT, "--ssl-keyfile", DEFAULT_KEY]
        # Trust self-signed cert for readiness check unless caller provided explicit CA bundle.
        request_verify = os.getenv("REQUESTS_CA_BUNDLE", DEFAULT_CERT)

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
            requests.get(f"{api_base}/docs", timeout=1, verify=request_verify)
            break
        except requests.RequestException:
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
    env = os.environ.copy()
    if api_scheme == "https" and "REQUESTS_CA_BUNDLE" not in env:
        env["REQUESTS_CA_BUNDLE"] = DEFAULT_CERT

    try:
        proc = subprocess.Popen(["python3", "-m", "app.listener"], env=env)
    except FileNotFoundError:
        proc = subprocess.Popen(["python", "-m", "app.listener"], env=env)
    wait_for_port("127.0.0.1", 2575, timeout=10)
    yield
    proc.terminate()
    proc.wait()
