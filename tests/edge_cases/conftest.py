import os
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import pytest
import requests

from app.core.config import (
    API_URL, 
    API_BIND_HOST, 
    API_BIND_PORT, 
    DOWNSTREAM_API_URL, 
    DOWNSTREAM_API_HOST, 
    DOWNSTREAM_API_PORT, 
    HL7_HOST, 
    HL7_PORT
)

CA_CERT_PATH = os.path.abspath("certs/stub.crt")

def _normalize_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


# Read from app/core/config.py (which already reads .env)
_api = urlparse(API_URL)
_stub = urlparse(DOWNSTREAM_API_URL)

def _wait_for_port(host: str, port: int, timeout: int = 10) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for {host}:{port}")


def _verify_for_url(url: str) -> str | bool:
    # Only provide CA bundle for HTTPS endpoints.
    return CA_CERT_PATH if urlparse(url).scheme == "https" else True


def _wait_for_http(url: str, timeout: int = 10, verify: str | bool = True) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            requests.get(url, timeout=1, verify=verify)
            return
        except requests.RequestException:
            time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for HTTP readiness: {url}")


def _popen(cmd: list[str], env: dict | None = None) -> subprocess.Popen:
    if sys.platform == "win32":
        return subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait(timeout=10)


@pytest.fixture(scope="session", autouse=True)
def start_stub_api(): # starts a simple HTTPS REST API server to act as the downstream API for integration tests
    cmd = [
        "uvicorn",
        "app.stub_api:app",
        "--host",
        DOWNSTREAM_API_HOST,
        "--port",
        str(DOWNSTREAM_API_PORT),
        "--ssl-keyfile", "certs/stub.key",
        "--ssl-certfile", "certs/stub.crt",
        "--log-config",
        "logging_config.json",
    ]
    proc = _popen(cmd)
    try:
        _wait_for_http(DOWNSTREAM_API_URL, timeout=15, verify=_verify_for_url(DOWNSTREAM_API_URL))
        yield
    finally:
        _stop_process(proc)


@pytest.fixture(scope="session", autouse=True)
def start_backend(start_stub_api):
    env = os.environ.copy()
    env["API_URL"] = f"{API_URL}"

    # Ensure backend trusts the stub cert for outbound HTTPS
    env["DOWNSTREAM_CA_BUNDLE"] = CA_CERT_PATH

    # Ensure backend calls a routable + cert-matching host (not 0.0.0.0)
    stub_host = _normalize_host(_stub.hostname or DOWNSTREAM_API_HOST)
    stub_port = _stub.port or DOWNSTREAM_API_PORT
    stub_path = _stub.path or ""
    env["DOWNSTREAM_API_URL"] = f"https://{stub_host}:{stub_port}{stub_path}"

    cmd = [
        "uvicorn",
        "app.api:app",
        "--host",
        API_BIND_HOST,
        "--port",
        str(API_BIND_PORT),
        "--log-config", "logging_config.json",
    ]

    proc = _popen(cmd, env=env)
    try:
        _wait_for_http(API_URL, timeout=15, verify=_verify_for_url(API_URL))
        yield
    finally:
        _stop_process(proc)


@pytest.fixture(scope="session", autouse=True)
def start_listener(start_backend):
    env = os.environ.copy()
    env["LISTENER"] = f"{HL7_HOST}:{HL7_PORT}"  # HL7 listener bind target

    cmd = ["python3", "-m", "app.listener"]
    try:
        proc = _popen(cmd, env=env)
    except FileNotFoundError:
        proc = _popen(["python", "-m", "app.listener"], env=env)

    try:
        _wait_for_port(HL7_HOST, HL7_PORT, timeout=15)
        yield
    finally:
        _stop_process(proc)
