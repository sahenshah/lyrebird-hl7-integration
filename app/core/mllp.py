import logging
from app.core.config import MAX_FRAMING_ERRORS, MAX_BUFFER_SIZE

MLLP_START_BYTE = b"\x0b"
MLLP_END_BYTES = b"\x1c\x0d"

def frame_message(message: str) -> bytes:
    return MLLP_START_BYTE + message.encode("utf-8") + MLLP_END_BYTES

def deframe_message(data: bytes) -> str:
    if not data.startswith(MLLP_START_BYTE) or not data.endswith(MLLP_END_BYTES):
        raise ValueError("Invalid MLLP framing")
    # strip exact start/end
    stripped = data[len(MLLP_START_BYTE):-len(MLLP_END_BYTES)]
    return stripped.decode("utf-8")

def extract_messages_from_buffer(buffer: bytes, framing_error_count=0):
    messages = []
    errors = framing_error_count

    while True:
        if len(buffer) > MAX_BUFFER_SIZE:
            logging.error("Buffer size exceeded maximum limit. Clearing buffer.")
            return messages, b"", errors  # Optionally, close connection at caller

        start_index = buffer.find(MLLP_START_BYTE)
        end_index = buffer.find(MLLP_END_BYTES)

        if start_index == -1 or end_index == -1:
            break

        if end_index < start_index:
            errors += 1
            logging.warning(f"Framing error detected ({errors}/{MAX_FRAMING_ERRORS}). Discarding data before end marker.")
            buffer = buffer[end_index + len(MLLP_END_BYTES):]
            if errors >= MAX_FRAMING_ERRORS:
                logging.error("Too many framing errors. Clearing buffer.")
                return messages, b"", errors  # Optionally, close connection at caller
            continue

        raw_message = buffer[start_index + len(MLLP_START_BYTE):end_index]
        messages.append(raw_message.decode("utf-8"))
        buffer = buffer[end_index + len(MLLP_END_BYTES):]
        errors = 0  # Reset error count after successful extraction

    return messages, buffer, errors