import socket
import logging
import logging.config
import json
import requests
import time
import threading
from pathlib import Path
from urllib.parse import urlparse
from app.core.retry import retry

from hl7apy.parser import parse_message
from app.core.config import (
    HL7_HOST, 
    HL7_PORT, 
    API_URL, 
    API_TIMEOUT, 
    API_CA_BUNDLE,
    MAX_RETRIES, 
    RETRY_BACKOFF_BASE, 
    MAX_FRAMING_ERRORS, 
    MAX_BUFFER_SIZE,
    MAX_MESSAGE_SIZE,
    IDEMPOTENCY_TTL_SECONDS,
    IDEMPOTENCY_MAXSIZE,
)
from app.core.mllp import deframe_message, frame_message, extract_messages_from_buffer
from app.core.ack import build_ack
from app.services.transformer import transform_hl7_to_json, normalize_hl7_segments
from hl7apy.consts import VALIDATION_LEVEL
from app.core.idempotency import IdempotencyGuard

guard = IdempotencyGuard(
    ttl_seconds=IDEMPOTENCY_TTL_SECONDS,
    maxsize=IDEMPOTENCY_MAXSIZE,
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def configure_logging() -> None:
    config_path = PROJECT_ROOT / "logging_config.json"
    if not config_path.exists():
        logging.basicConfig(level=logging.INFO)
        return
    with config_path.open("r", encoding="utf-8") as config_file:
        logging.config.dictConfig(json.load(config_file))


configure_logging()

# Structured logging setup
class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "message_control_id"):
            record.message_control_id = ""
        if not hasattr(record, "patient_id"):
            record.patient_id = ""
        if not hasattr(record, "message_type"):
            record.message_type = ""
        if not hasattr(record, "source_addr"):
            record.source_addr = ""
        return True

logger = logging.getLogger("hl7_listener")
logger.addFilter(ContextFilter())

def get_logger_with_context(message_control_id="", patient_id="", message_type="", source_addr=""):
    return logging.LoggerAdapter(
        logger,
        {
            "message_control_id": message_control_id,
            "patient_id": patient_id,
            "message_type": message_type,
            "source_addr": source_addr
        }
    )

def send_to_api(payload):
    """
    Sends the given payload to the configured API endpoint using a POST request.
    Automatically retries on transient network errors using exponential backoff,
    with retry parameters loaded from environment variables.

    Args:
        payload (dict): The JSON-serializable payload to send.

    Returns:
        requests.Response: The response object from the API call.

    Raises:
        requests.RequestException: If all retry attempts fail.
    """
    parsed_url = urlparse(API_URL)
    verify_tls: str | bool = True
    if parsed_url.scheme == "https" and API_CA_BUNDLE:
        if not Path(API_CA_BUNDLE).exists():
            raise FileNotFoundError(f"API_CA_BUNDLE not found: {API_CA_BUNDLE}")
        verify_tls = API_CA_BUNDLE

    def call_api():
        response = requests.post(
                       API_URL,
                       json=payload,
                       timeout=API_TIMEOUT,
                       verify=verify_tls,
                   )
        response.raise_for_status()
        return response

    return retry(
        call_api,
        max_attempts=MAX_RETRIES,
        backoff_base=RETRY_BACKOFF_BASE,
        exceptions=(requests.RequestException,),
        logger=logger
    )

def process_hl7_message(hl7_string, conn, addr):
    start = time.time()
    source_addr = f"{addr[0]}:{addr[1]}"
    log = get_logger_with_context(source_addr=source_addr)
    ack = "MSH|^~\\&|||||||ACK||P|2.3\rMSA|AE|\r"

    try:
        # Normalize segment separators before parsing
        hl7_string = normalize_hl7_segments(hl7_string)
        
        # --- Check Message Size ---
        if len(hl7_string) > MAX_MESSAGE_SIZE:
            raise ValueError("HL7 message too large")
            
        parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.STRICT)
        message_control_id = parsed.MSH.MSH_10.to_er7() if hasattr(parsed.MSH, "MSH_10") else "unknown"
        patient_id = parsed.PID.PID_3.to_er7() if hasattr(parsed, "PID") and hasattr(parsed.PID, "PID_3") else "unknown"
        message_type = parsed.MSH.MSH_9.to_er7() if hasattr(parsed.MSH, "MSH_9") else "unknown"

        # --- Whitelist message types ---
        allowed_types = {"ADT^A01"}
        if message_type not in allowed_types:
            raise ValueError(f"Unsupported message type: {message_type}")

        # --- Validate required fields ---
        control_id = parsed.MSH.MSH_10.value if hasattr(parsed.MSH, "MSH_10") else None
        if not control_id:
            raise ValueError("Missing message control ID")

        hl7_json = transform_hl7_to_json(parsed)

        if not guard.mark_if_new(control_id):
            log.info(f"[{control_id}] Duplicate message detected; returning ACK without reprocessing")
            ack = build_ack(parsed, ack_code="AA")
        else:
            try:
                send_to_api(hl7_json)
                ack = build_ack(parsed, ack_code="AA")
            except Exception as e:
                log.error(f"[{control_id}] Downstream processing failed after retries: {e}")
                guard.unmark(control_id)
                ack = build_ack(parsed, ack_code="AE")

    except Exception as e:
        log.error(f"Failed to process HL7 message: {e}")
        # keep fallback AE ack

    finally:
        conn.sendall(frame_message(ack))
        duration_ms = int((time.time() - start) * 1000)
        log.info(f"Processed in {duration_ms}ms")
        # DO NOT close conn here

def handle_connection(conn, addr):
    """
    Handles a single TCP connection:
    - Receives data in a buffer.
    - Extracts and processes complete HL7 messages.
    - Sends ACKs for each message.
    - Handles connection errors and closes the connection cleanly.
    """
    logger.info(f"Connection from {addr}")
    buffer = b""
    framing_error_count = 0
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buffer += data
            messages, buffer, framing_error_count = extract_messages_from_buffer(buffer, framing_error_count)
            if framing_error_count >= MAX_FRAMING_ERRORS or len(buffer) > MAX_BUFFER_SIZE:
                logger.error("Closing connection due to repeated framing errors or buffer overflow.")
                break
            for message_str in messages:
                process_hl7_message(message_str, conn, addr)
    except Exception as e:
        logger.exception("Connection error")
    finally:
        conn.close()
        logger.info(f"Connection closed from {addr}")

def start_listener(host=HL7_HOST, port=HL7_PORT):
    """
    Starts the TCP listener for incoming HL7 messages over MLLP.
    Each connection is handled in a separate thread.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        logger.info(f"Listening on {host}:{port}")

        while True:
            conn, addr = server.accept()
            thread = threading.Thread(
                target=handle_connection,
                args=(conn, addr),
                daemon=True
            )
            thread.start()

if __name__ == "__main__":
    # Entry point: start the HL7 listener service
    start_listener()