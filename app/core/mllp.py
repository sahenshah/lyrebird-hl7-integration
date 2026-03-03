MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"

def frame_message(message: str) -> bytes:
    return MLLP_START + message.encode("utf-8") + MLLP_END

def deframe_message(data: bytes) -> str:
    if not data.startswith(MLLP_START) or not data.endswith(MLLP_END):
        raise ValueError("Invalid MLLP framing")
    # strip exact start/end
    stripped = data[len(MLLP_START):-len(MLLP_END)]
    return stripped.decode("utf-8")