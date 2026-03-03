import socket
import logging
import requests

from hl7apy.parser import parse_message
from app.core.config import HOST, PORT, API_URL, API_TIMEOUT
from app.core.mllp import deframe_message, frame_message
from app.core.ack import build_ack
from app.services.transformer import transform_hl7_to_json
from hl7apy.consts import VALIDATION_LEVEL

logging.basicConfig(level=logging.INFO)


def send_to_api(payload):
    response = requests.post(API_URL, json=payload, timeout=API_TIMEOUT)
    response.raise_for_status()


def start_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        logging.info(f"Listening on {HOST}:{PORT}")

        while True:
            conn, addr = server.accept()
            with conn:
                logging.info(f"Connection from {addr}")
                data = conn.recv(4096)

                try:
                    hl7_string = deframe_message(data)
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

                    ack = build_ack(parsed, "AA")
                    logging.debug(f"ACK message returned by build_ack:\n{ack!r}")

                except Exception as e:
                    logging.error(f"Processing error: {e}")
                    try:
                        parsed = parse_message(hl7_string, validation_level=VALIDATION_LEVEL.TOLERANT)
                        logging.debug("HL7 message parsed for error ACK.")
                        ack = build_ack(parsed, "AE")
                    except Exception as parse_e:
                        logging.error(f"parse_message failed in exception handler: {parse_e}")
                        # Fallback ACK construction
                        ack = "MSH|^~\\&|||||||ACK||P|2.3\rMSA|AE|\r"

                conn.sendall(frame_message(ack))


if __name__ == "__main__":
    start_listener()