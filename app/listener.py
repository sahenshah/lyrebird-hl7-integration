import socket
import logging
import requests
import time

from hl7apy.parser import parse_message
from app.core.config import HOST, PORT, API_URL, API_TIMEOUT
from app.core.mllp import (
    deframe_message,
    frame_message,
    extract_messages_from_buffer,
    MAX_FRAMING_ERRORS,
    MAX_BUFFER_SIZE,
)
from app.core.ack import build_ack
from app.services.transformer import transform_hl7_to_json
from hl7apy.consts import VALIDATION_LEVEL

# Structured logging setup
class ContextFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "control_id"):
            record.control_id = ""
        if not hasattr(record, "patient_id"):
            record.patient_id = ""
        if not hasattr(record, "message_type"):
            record.message_type = ""
        if not hasattr(record, "source_addr"):
            record.source_addr = ""
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(control_id)s %(patient_id)s %(message_type)s %(source_addr)s] %(message)s'
)
logger = logging.getLogger("hl7_listener")
logger.addFilter(ContextFilter())
logging.getLogger().addFilter(ContextFilter())  # Also add to root logger if needed

def get_logger_with_context(control_id="", patient_id="", message_type="", source_addr=""):
    return logging.LoggerAdapter(
        logger,
        {
            "control_id": control_id,
            "patient_id": patient_id,
            "message_type": message_type,
            "source_addr": source_addr
        }
    )

def send_to_api(payload):
    """
    Sends the transformed HL7 payload as JSON to the configured API endpoint.
    Raises an exception if the request fails.
    """
    response = requests.post(API_URL, json=payload, timeout=API_TIMEOUT)
    response.raise_for_status()

def process_hl7_message(hl7_string, conn, addr):
    """
    Processes a single HL7 message string:
    - Parses the HL7 message.
    - Transforms it to JSON.
    - Sends the JSON to the API.
    - Builds and sends an ACK (positive or error) back to the sender.
    """
    start = time.time()
    source_addr = f"{addr[0]}:{addr[1]}"
    log = get_logger_with_context()
    try:
        parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.TOLERANT)
        control_id = parsed.MSH.MSH_10.to_er7() if hasattr(parsed.MSH, "MSH_10") else "unknown"
        patient_id = parsed.PID.PID_3.to_er7() if hasattr(parsed, "PID") and hasattr(parsed.PID, "PID_3") else "unknown"
        message_type = parsed.MSH.MSH_9.to_er7() if hasattr(parsed.MSH, "MSH_9") else "unknown"
        log = get_logger_with_context(control_id, patient_id, message_type, source_addr)

        log.info(f"Processing message from {addr}")

        payload = transform_hl7_to_json(parsed)
        log.info("Transformed payload, sending to API")
        send_to_api(payload)
        ack = build_ack(parsed, "AA")  # AA = Application Accept
        log.info("Message successfully processed, returning ACK")

    except Exception as e:
        log.error(f"Processing error: {e}")
        try:
            parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.TOLERANT)
            ack = build_ack(parsed, "AE")  # AE = Application Error
        except Exception as parse_e:
            log.error(f"parse_message failed in exception handler: {parse_e}")
            # Fallback ACK construction if parsing fails
            ack = "MSH|^~\\&|||||||ACK||P|2.3\rMSA|AE|\r"
    finally:
        duration_ms = int((time.time() - start) * 1000)
        log.info(f"Processed in {duration_ms}ms")
        # Send the ACK message back to the client, framed with MLLP
        conn.sendall(frame_message(ack))

def start_listener():
    """
    Starts the TCP listener for incoming HL7 messages over MLLP.
    For each connection:
    - Receives data in a buffer.
    - Extracts and processes complete HL7 messages.
    - Sends ACKs for each message.
    - Handles connection errors and closes the connection cleanly.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        logger.info(f"Listening on {HOST}:{PORT}")

        while True:
            conn, addr = server.accept()
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

if __name__ == "__main__":
    # Entry point: start the HL7 listener service
    start_listener()