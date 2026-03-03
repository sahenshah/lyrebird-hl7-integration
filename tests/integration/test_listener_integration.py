import socket
import threading
import time
import requests
import pytest

from app.listener import start_listener
from app.core.mllp import frame_message


@pytest.fixture(scope="module", autouse=True)
def start_server():
    """
    Starts the HL7 listener in a background thread for integration tests.
    """
    thread = threading.Thread(target=start_listener, daemon=True)
    thread.start()
    time.sleep(1)
    yield


def test_listener_returns_ack(monkeypatch):
    """
    Sends a valid HL7 message to the listener and verifies an AA ACK is returned.
    API call is mocked.
    """
    monkeypatch.setattr(
        "app.listener.send_to_api",
        lambda payload: None
    )

    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01|123456|P|2.3\r"
        "PID|1||MRN123||Doe^John\r"
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", 2575))
        s.sendall(frame_message(hl7))
        data = s.recv(4096)

    assert b"MSA|AA|123456" in data


def test_listener_returns_ae_for_invalid_hl7(monkeypatch):
    """
    Sends a malformed HL7 message to the listener and verifies an AE ACK is returned.
    API call is mocked.
    """
    monkeypatch.setattr(
        "app.listener.send_to_api",
        lambda payload: None
    )

    invalid_hl7 = "THIS IS NOT HL7\r"

    from app.core.mllp import frame_message

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", 2575))
        s.sendall(frame_message(invalid_hl7))
        data = s.recv(4096)

    assert b"MSA|AE" in data

def test_listener_returns_ae_when_api_fails(monkeypatch):
    """
    Simulate downstream API failure and expect AE ACK.
    """

    # Force API call to fail
    def mock_api_failure(payload):
        raise Exception("API unavailable")

    monkeypatch.setattr(
        "app.listener.send_to_api",
        mock_api_failure
    )

    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01|999999|P|2.3\r"
        "PID|1||MRN999||Doe^Jane\r"
    )

    from app.core.mllp import frame_message

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", 2575))
        s.sendall(frame_message(hl7))
        data = s.recv(4096)

    assert b"MSA|AE|999999" in data