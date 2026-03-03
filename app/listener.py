import socket
import logging
import requests

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

logging.basicConfig(level=logging.INFO)

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
    try:
        logging.debug(f"Deframed HL7 string:\n{hl7_string!r}")
        try:
            parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.TOLERANT)
            logging.debug("HL7 message parsed successfully.")
        except Exception as parse_e:
            logging.error(f"parse_message failed: {parse_e}")
            raise

        logging.debug("Calling transform_hl7_to_json...")
        payload = transform_hl7_to_json(parsed)
        logging.debug(f"Payload: {payload}")

        logging.debug("Sending to API...")
        send_to_api(payload)
        logging.debug("API call successful.")

        ack = build_ack(parsed, "AA")  # AA = Application Accept
        logging.debug(f"ACK message returned by build_ack:\n{ack!r}")

    except Exception as e:
        logging.error(f"Processing error: {e}")
        try:
            parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.TOLERANT)
            logging.debug("HL7 message parsed for error ACK.")
            ack = build_ack(parsed, "AE")  # AE = Application Error
        except Exception as parse_e:
            logging.error(f"parse_message failed in exception handler: {parse_e}")
            # Fallback ACK construction if parsing fails
            ack = "MSH|^~\\&|||||||ACK||P|2.3\rMSA|AE|\r"

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
        logging.info(f"Listening on {HOST}:{PORT}")

        while True:
            conn, addr = server.accept()
            logging.info(f"Connection from {addr}")
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
                        logging.error("Closing connection due to repeated framing errors or buffer overflow.")
                        break
                    for message_str in messages:
                        process_hl7_message(message_str, conn, addr)
            except Exception as e:
                logging.exception("Connection error")
            finally:
                conn.close()
                logging.info(f"Connection closed from {addr}")

if __name__ == "__main__":
    # Entry point: start the HL7 listener service
    start_listener()