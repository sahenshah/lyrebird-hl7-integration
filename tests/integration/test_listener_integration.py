import socket
import threading
import time
import requests
import pytest
from hl7apy.parser import parse_message

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


@pytest.fixture(autouse=True)
def clear_idempotency_guard():
    from app import listener
    if hasattr(listener, "guard"):
        listener.guard.clear()


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

def test_listener_sends_expected_json(monkeypatch):
    """
    Sends a valid HL7 message and verifies the JSON payload sent to the API.
    Uses the already running listener and avoids starting a new one.
    """
    captured_payload = {}

    def mock_post(url, json, timeout):
        captured_payload.clear()
        captured_payload.update(json)
        class Response:
            status_code = 200
            def raise_for_status(self): pass
        return Response()

    monkeypatch.setattr("requests.post", mock_post)

    expected_payload = {
        "message_control_id": "123456",
        "message_type": "ADT^A01",
        "timestamp": "202603021200",
        "patient": {
            "mrn": "MRN12345",
            "first_name": "John",
            "last_name": "Doe",
            "dob": "19900101",
            "sex": "M"
        },
        "source": {
            "sending_app": "SendingApp",
            "sending_facility": "SendingFacility"
        }
    }

    # Read and normalize HL7 message
    hl7 = open("examples/sample_adt_a01.hl7").read().replace("\n", "\r")
    # Send HL7 message and receive ACK
    with socket.create_connection(("127.0.0.1", 2575)) as sock:
        sock.sendall(frame_message(hl7))
        sock.recv(4096)
    # Wait briefly to ensure mock_post is called before assertion
    time.sleep(0.2)
    assert captured_payload == expected_payload

def test_listener_skips_duplicate(monkeypatch):
    """
    Send the same HL7 message twice.
    API should only be called once.
    """

    call_count = 0

    def mock_post(url, json, timeout):
        nonlocal call_count
        call_count += 1

        class Response:
            status_code = 200
            def raise_for_status(self): pass

        return Response()

    monkeypatch.setattr("requests.post", mock_post)

    hl7 = open("examples/sample_adt_a01.hl7").read().replace("\n", "\r")

    # Send message first time
    with socket.create_connection(("127.0.0.1", 2575)) as sock:
        sock.sendall(frame_message(hl7))
        sock.recv(4096)

    # Send same message again
    with socket.create_connection(("127.0.0.1", 2575)) as sock:
        sock.sendall(frame_message(hl7))
        sock.recv(4096)

    assert call_count == 1

def test_failed_api_does_not_mark_processed(monkeypatch):
    call_count = 0

    def mock_post(url, json, timeout):
        nonlocal call_count
        call_count += 1
        raise Exception("API failure")

    monkeypatch.setattr("requests.post", mock_post)

    hl7 = open("examples/sample_adt_a01.hl7").read().replace("\n", "\r")

    # Send twice — both should attempt API
    for _ in range(2):
        with socket.create_connection(("127.0.0.1", 2575)) as sock:
            sock.sendall(frame_message(hl7))
            sock.recv(4096)

    assert call_count == 2