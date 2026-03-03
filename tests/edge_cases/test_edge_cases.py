import socket
import time
import pytest
from app.core.mllp import frame_message, deframe_message, extract_messages_from_buffer

HL7_HOST = "127.0.0.1"
HL7_PORT = 2575

def send_hl7_message(message: str):
    """Helper to send a single HL7 message to the listener and receive ACK."""
    with socket.create_connection((HL7_HOST, HL7_PORT)) as sock:
        sock.sendall(frame_message(message))
        ack = sock.recv(4096)
    return ack

@pytest.mark.edge
def test_large_hl7_message():
    """Send a very large HL7 message (~500 KB) to test buffer handling."""
    base_message = (
        "MSH|^~\\&|TestApp|TestFac|RecvApp|RecvFac|20260303||ADT^A01|123456|P|2.3\r"
        "PID|1||MRN12345||Doe^John||19900101|M\r"
    )
    # Repeat to make ~500 KB
    repeated = base_message * 5000
    ack = send_hl7_message(repeated)
    assert b"MSA|AA|" in ack, "Large message should return ACK"

@pytest.mark.edge
def test_malformed_hl7_message():
    """Send a malformed HL7 message to test AE response."""
    malformed = "MSH|^~\\&|BadApp|BadFac||RecvFac|20260303||ADT^A01||P|2.3\rPID|1|||"
    ack = send_hl7_message(malformed)
    # AE expected because PID is incomplete
    assert b"MSA|AE|" in ack, "Malformed message should return AE"

@pytest.mark.edge
def test_multiple_back_to_back_messages():
    """Send 3 messages in one TCP packet to test streaming buffer handling."""
    messages = []
    for i in range(3):
        msg = (
            f"MSH|^~\\&|App{i}|Fac{i}|RecvApp|RecvFac|20260303||ADT^A01|ID{i}|P|2.3\r"
            f"PID|1||MRN{i}||Doe^John||19900101|M\r"
        )
        messages.append(frame_message(msg))
    combined = b"".join(messages)

    with socket.create_connection((HL7_HOST, HL7_PORT)) as sock:
        sock.settimeout(2)
        sock.sendall(combined)
        data = b""
        # Try to read all ACKs within a timeout window
        start = time.time()
        while time.time() - start < 2:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            except socket.timeout:
                break
        
        # Extract all messages (ACKs) from the buffer
        acks, remaining, errors = extract_messages_from_buffer(data)
        assert len(acks) == 3, "Should receive 3 ACKs"


        for i, ack in enumerate(acks):
            assert f"MSA|AA|ID{i}".encode() in ack.encode()