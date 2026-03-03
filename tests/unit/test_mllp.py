"""
This test suite proves:

- Correct framing of HL7 messages
- Handling of multiple messages in a buffer
- No leftover buffer corruption after extraction
"""

from app.core.mllp import frame_message, deframe_message, extract_messages_from_buffer


def test_frame_and_deframe_roundtrip():
    message = "MSH|^~\\&|Test\rPID|1||123\r"
    framed = frame_message(message)
    deframed = deframe_message(framed)
    assert deframed == message


def test_extract_multiple_messages():
    msg1 = frame_message("MSH|^~\\&|A\r")
    msg2 = frame_message("MSH|^~\\&|B\r")
    buffer = msg1 + msg2

    messages, remainder, _ = extract_messages_from_buffer(buffer)

    assert len(messages) == 2
    assert remainder == b""