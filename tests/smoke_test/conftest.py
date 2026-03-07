"""Shared fixtures for smoke tests."""
import pytest
import subprocess
import time
import requests
import os
import signal
import json
from pathlib import Path
from typing import Dict, Generator, List, Optional
import uuid

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return project root directory."""
    return Path(__file__).parent.parent.parent

@pytest.fixture(scope="session")
def logs_dir(project_root) -> Path:
    """Return logs directory."""
    logs = project_root / "logs"
    logs.mkdir(exist_ok=True)
    return logs

@pytest.fixture(scope="session")
def audit_log_path(logs_dir) -> Path:
    """Return path to publisher audit log."""
    return logs_dir / "publisher_audit.jsonl"

@pytest.fixture(scope="session")
def example_message(project_root) -> Path:
    """Return path to example HL7 message."""
    return project_root / "examples" / "sample_adt_a01.hl7"

@pytest.fixture(scope="session")
def ports():
    """Return port configuration."""
    return {
        "backend": 8000,
        "downstream": 9000,
        "listener": 2575
    }

@pytest.fixture(scope="session")
def urls(ports):
    """Return URL configuration."""
    return {
        "backend": f"http://localhost:{ports['backend']}",
        "backend_health": f"http://localhost:{ports['backend']}/health",
        "backend_messages": f"http://localhost:{ports['backend']}/api/v1/messages",
        "downstream": f"https://localhost:{ports['downstream']}",
        "downstream_receive": f"https://localhost:{ports['downstream']}/receive"
    }

@pytest.fixture(scope="session")
def cleanup_after_suite():
    """Cleanup after all tests."""
    yield
    # Kill any remaining processes
    subprocess.run("pkill -f 'uvicorn|python3 -m app.listener'", shell=True)
    subprocess.run("docker compose down -v", shell=True, cwd=Path(__file__).parent.parent.parent)

class ServiceManager:
    """Manages service lifecycle for tests."""
    
    def __init__(self, project_root: Path, urls: Dict):
        self.project_root = project_root
        self.urls = urls
        self.processes = []
    
    def start_downstream(self):
        """Start downstream stub API."""
        # Generate certs if needed
        cert_dir = self.project_root / "certs"
        cert_dir.mkdir(exist_ok=True)
        
        if not (cert_dir / "stub.crt").exists():
            subprocess.run([
                "openssl", "req", "-x509", "-nodes", "-days", "365",
                "-newkey", "rsa:2048",
                "-keyout", str(cert_dir / "stub.key"),
                "-out", str(cert_dir / "stub.crt"),
                "-config", str(cert_dir / "openssl-stub.cnf")
            ], check=True)
        
        # Start downstream
        proc = subprocess.Popen([
            "uvicorn", "app.stub_api:app",
            "--host", "0.0.0.0",
            "--port", "9000",
            "--ssl-keyfile", str(cert_dir / "stub.key"),
            "--ssl-certfile", str(cert_dir / "stub.crt"),
            "--log-level", "warning"
        ], cwd=self.project_root)
        self.processes.append(proc)
        self._wait_for_service(self.urls["downstream_receive"], "downstream")
    
    def start_backend(self):
        """Start backend with Docker."""
        subprocess.run([
            "docker", "compose", "up", "--build", "-d"
        ], cwd=self.project_root, check=True)
        self._wait_for_service(self.urls["backend_health"], "backend")
    
    def start_listener(self):
        """Start HL7 listener."""
        proc = subprocess.Popen([
            "python3", "-m", "app.listener"
        ], cwd=self.project_root)
        self.processes.append(proc)
        time.sleep(2)  # Give listener time to bind
    
    def _wait_for_service(self, url: str, name: str, timeout: int = 30):
        """Wait for service to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                if "https" in url:
                    requests.get(url, verify=False, timeout=1)
                else:
                    requests.get(url, timeout=1)
                print(f"✅ {name} ready")
                return
            except:
                time.sleep(1)
        raise TimeoutError(f"{name} not ready after {timeout}s")
    
    def kill_downstream(self):
        """Kill downstream API."""
        subprocess.run("lsof -ti:9000 | xargs kill -9", shell=True)
        time.sleep(1)
        # Verify it's dead
        try:
            requests.post(self.urls["downstream_receive"], json={}, verify=False, timeout=1)
            raise AssertionError("Downstream still alive")
        except:
            pass
    
    def restart_downstream(self):
        """Restart downstream API."""
        self.start_downstream()  # Will start a new one
    
    def cleanup(self):
        """Clean up all processes."""
        for proc in self.processes:
            proc.terminate()
        subprocess.run("docker compose down -v", shell=True, cwd=self.project_root)
        subprocess.run("pkill -f 'uvicorn|python3 -m app.listener'", shell=True)

@pytest.fixture(scope="module")
def services(project_root, urls, cleanup_after_suite):
    """Start all services for tests."""
    manager = ServiceManager(project_root, urls)
    manager.start_downstream()
    manager.start_backend()
    manager.start_listener()
    yield manager
    manager.cleanup()

class MessageSender:
    """Helper for sending HL7 messages."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.last_output = ""
        self.last_control_id = None
    
    def send(self, message_path: Path, expected_pattern: str = "MSA|AA") -> Dict:
        """Send message and return result."""
        result = subprocess.run([
            "python3", "-m", "app.sender",
            "--file", str(message_path),
            "--quiet"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.last_output = result.stdout
        
        # Extract control ID
        import re
        match = re.search(r"MSA\|[A-Z]+\|([^\|]+)", result.stdout)
        if match:
            self.last_control_id = match.group(1)
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "control_id": self.last_control_id,
            "success": expected_pattern in result.stdout
        }
    
    def send_and_expect(self, message_path: Path, expected_pattern: str) -> str:
        """Send message and assert expected pattern."""
        result = self.send(message_path, expected_pattern)
        assert expected_pattern in result["stdout"], \
            f"Expected {expected_pattern} in output, got: {result['stdout']}"
        return result["control_id"]

@pytest.fixture
def sender(project_root):
    """Return message sender helper."""
    return MessageSender(project_root)

@pytest.fixture(autouse=True)
def clear_audit_log(audit_log_path):
    """Clear audit log before each test."""
    if audit_log_path.exists():
        audit_log_path.unlink()
    yield