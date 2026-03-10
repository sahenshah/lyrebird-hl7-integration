import logging
from app.core.config import MAX_FRAMING_ERRORS, MAX_BUFFER_SIZE

logger = logging.getLogger("app.core.mllp")

MLLP_START_BYTE = b"\x0b"
MLLP_END_BYTES = b"\x1c\x0d"

def frame_message(message: str) -> bytes:
    """Wrap an HL7 payload string in MLLP framing bytes (VT ... FS+CR) for transport."""
    return MLLP_START_BYTE + message.encode("utf-8") + MLLP_END_BYTES

def deframe_message(data: bytes) -> str:
    """Validate MLLP framing and return the inner HL7 payload as a UTF-8 string."""
    if not data.startswith(MLLP_START_BYTE) or not data.endswith(MLLP_END_BYTES):
        raise ValueError("Invalid MLLP framing")
    # strip exact start/end
    stripped = data[len(MLLP_START_BYTE):-len(MLLP_END_BYTES)]
    return stripped.decode("utf-8")

def extract_messages_from_buffer(buffer: bytes, framing_error_count=0):
    """
    Parse a rolling TCP buffer, extract complete MLLP-framed HL7 messages in order,
    and return (messages, remaining_buffer, updated_error_count).
    """
    messages = []
    errors = framing_error_count

    while True:
        if len(buffer) > MAX_BUFFER_SIZE:
            logger.error("Buffer size exceeded maximum limit. Clearing buffer.")
            return messages, b"", errors

        start_index = buffer.find(MLLP_START_BYTE)
        if start_index == -1:
            # No frame start present; discard noise
            return messages, b"", errors

        if start_index > 0:
            # Drop noise before start marker
            buffer = buffer[start_index:]
            start_index = 0

        end_index = buffer.find(MLLP_END_BYTES, start_index + len(MLLP_START_BYTE))
        if end_index == -1:
            # Incomplete frame; keep for next recv
            return messages, buffer, errors

        raw_message = buffer[start_index + len(MLLP_START_BYTE):end_index]
        try:
            messages.append(raw_message.decode("utf-8"))
            errors = 0
        except UnicodeDecodeError:
            errors += 1
            logger.warning(f"UTF-8 decode error ({errors}/{MAX_FRAMING_ERRORS}). Dropping frame.")
            if errors >= MAX_FRAMING_ERRORS:
                logger.error("Too many framing/decode errors. Clearing buffer.")
                return messages, b"", errors

        buffer = buffer[end_index + len(MLLP_END_BYTES):]