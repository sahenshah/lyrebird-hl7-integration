"""
HL7 Message Publisher

A robust HL7 message sender that simulates an upstream clinical system.
Features scheduled publishing, connection retries, and audit logging.
"""

import socket
import time
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json
from app.core.mllp import frame_message, deframe_message, MLLP_START_BYTE, MLLP_END_BYTES
from app.core.config import (
    MAX_BUFFER_SIZE,
    MAX_MESSAGE_SIZE 
)

logger = logging.getLogger("hl7_publisher")
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.CRITICAL)
logger.propagate = False

class HL7Publisher:
    """HL7 message publisher with retry logic and audit logging."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 2575,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        connection_timeout: int = 10,
        audit_log_path: Optional[Path] = None
    ):
        self.host = host
        self.port = port
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout
        self.buffer_size = MAX_BUFFER_SIZE
        self.max_message_size = MAX_MESSAGE_SIZE
        self.audit_log: list[Dict[str, Any]] = []
        self.last_ack_message: Optional[str] = None
        self._seen_successful_control_ids: set[str] = set()

        if audit_log_path:
            self.audit_log_path = Path(audit_log_path)
        else:
            self.audit_log_path = Path(__file__).parent.parent / "logs" / "publisher_audit.jsonl"

        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_seen_successful_control_ids()  # <- add

    def _load_seen_successful_control_ids(self) -> None:
        # Rehydrate known-success message control IDs from prior audit logs
        # so repeat sends can be classified as skipped-already-processed.
        if not self.audit_log_path.exists():
            return
        try:
            with open(self.audit_log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    cid = entry.get("message_control_id")
                    status = entry.get("status")
                    success = entry.get("success")
                    if cid and (status in {"success", "skipped_already_processed"} or success is True):
                        self._seen_successful_control_ids.add(cid)
        except Exception:
            # keep sender resilient; ignore audit parse errors
            pass

    def _connect_and_send(self, framed_message: bytes) -> bytes:
        """Establish connection and send message (used by retry wrapper)."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.connection_timeout)
            sock.connect((self.host, self.port))
            sock.sendall(framed_message)
            
            response = _recv_full_mllp_frame(
                sock,
                buffer_size=self.buffer_size,
                max_bytes=self.max_message_size,
            )
            return response
    
    def send_message(self, message: str, message_control_id: Optional[str] = None) -> bool:
        """
        Send an HL7 message with retry logic.
        
        Args:
            message: Raw HL7 message (segments separated by \r)
            message_control_id: Optional control ID for audit logging
            
        Returns:
            bool: True if successful, False after all retries fail
        """
        framed = frame_message(message)
        
        # Extract control ID from message if not provided
        if not message_control_id:
            # Simple extraction from MSH-10
            for segment in message.split('\r'):
                if segment.startswith('MSH'):
                    parts = segment.split('|')
                    if len(parts) > 9:
                        message_control_id = parts[9]
                    break
        
        was_seen_before_send = bool(message_control_id) and (
            message_control_id in self._seen_successful_control_ids
        )

        attempt = 0
        start_time = time.time()
        
        while attempt < self.retry_attempts:
            attempt += 1
            try:
                logger.info(f"Publishing message (attempt {attempt}/{self.retry_attempts})", 
                           extra={
                               "message_control_id": message_control_id,
                               "attempt": attempt,
                               "host": self.host,
                               "port": self.port
                           })
                
                response = self._connect_and_send(framed)

                ack_message = deframe_message(response)
                self.last_ack_message = ack_message

                ack_upper = ack_message.upper()
                is_success = "MSA|AA" in ack_upper
                is_duplicate_skip = is_success and was_seen_before_send

                status = (
                    "skipped_already_processed"
                    if is_duplicate_skip
                    else ("success" if is_success else "nack")
                )

                audit_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message_control_id": message_control_id,
                    "attempt": attempt,
                    "success": is_success,
                    "status": status,
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                    "ack_message": ack_message[:100] + "..." if len(ack_message) > 100 else ack_message
                }
                self.audit_log.append(audit_entry)

                if is_success and message_control_id:
                    self._seen_successful_control_ids.add(message_control_id)

                if is_success:
                    return True
                else:
                    logger.warning(
                        "Received NACK (AE) from receiver",
                        extra={"message_control_id": message_control_id, "attempt": attempt}
                    )

            except (socket.timeout, ConnectionRefusedError, socket.error) as e:
                logger.warning(f"Connection failed (attempt {attempt})", 
                              extra={
                                  "message_control_id": message_control_id,
                                  "error": str(e)
                              })
                
                # Audit log for failed attempt
                self.audit_log.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message_control_id": message_control_id,
                    "attempt": attempt,
                    "success": False,
                    "error": str(e)
                })
            
            # Wait before retry (except on last attempt)
            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay * attempt)  # Linear backoff
        
        logger.error(f"All {self.retry_attempts} attempts failed for message",
                    extra={"message_control_id": message_control_id})
        return False
    
    def publish_scheduled(self, message_path: Path, interval_seconds: int = 60, count: Optional[int] = None):
        """
        Publish messages on a schedule.
        
        Args:
            message_path: Path to HL7 message file
            interval_seconds: Seconds between publications
            count: Number of messages to publish (None = infinite)
        """
        # Load message template
        with open(message_path) as f:
            template = f.read().replace('\n', '\r')
        
        published = 0
        try:
            while count is None or published < count:
                # Replace timestamp in MSH segment
                import re
                now = datetime.now()
                current_time = now.strftime("%Y%m%d%H%M%S")
                
                # Update MSH-7 with current timestamp
                message = re.sub(
                    r'(MSH\|.*?\|.*?\|.*?\|.*?\|.*?\|)([^|]*)(\|.*)',
                    lambda m: m.group(1) + current_time + m.group(3),
                    template
                )
                
                # Update unique control ID (MSH-10)
                import uuid
                control_id = str(uuid.uuid4())[:8]
                message = re.sub(
                    r'(MSH\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|)([^|]*)(\|.*)',
                    lambda m: m.group(1) + control_id + m.group(3),
                    message
                )
                
                logger.info(f"Scheduled publication #{published + 1}",
                           extra={"message_control_id": control_id})
                
                success = self.send_message(message, control_id)
                
                if success:
                    if self.last_ack_message:
                        print(f"Received ACK message #{published + 1}:")
                        display_ack = self.last_ack_message.replace("\r", "\n").strip()
                        print(display_ack)
                    published += 1
                
                if count is None or published < count:
                    time.sleep(interval_seconds)
                    
        except KeyboardInterrupt:
            logger.info("Scheduled publishing stopped by user")
        
        finally:
            logger.info("Scheduled publishing stopped")
    
    def save_audit_log(self, path: Optional[Path] = None):
        """Append audit log entries to file as JSON lines."""
        save_path = path or self.audit_log_path
        try:
            with open(save_path, 'a') as f:
                for entry in self.audit_log:
                    f.write(json.dumps(entry) + "\n")
            logger.info(f"Audit log appended to {save_path}")
        except Exception as e:
            logger.error(f"Failed to append audit log: {e}")


def _recv_full_mllp_frame(sock, buffer_size: int = 4096, max_bytes: int = 1024 * 1024) -> bytes:
    # Read from socket until one complete MLLP-framed ACK/NACK is received.
    # Supports partial TCP reads and enforces a maximum frame size.
    data = b""
    while True:
        chunk = sock.recv(buffer_size)
        if not chunk:
            raise ConnectionError("Connection closed before full MLLP ACK was received")
        data += chunk

        if len(data) > max_bytes:
            raise ValueError("Received ACK exceeds maximum allowed size")

        start = data.find(MLLP_START_BYTE)
        if start == -1:
            continue

        end = data.find(MLLP_END_BYTES, start + 1)
        if end != -1:
            return data[start:end + len(MLLP_END_BYTES)]


def main():
    # Parse CLI arguments, run sender in single/scheduled mode, and persist audit entries on exit.
    parser = argparse.ArgumentParser(description="HL7 Message Publisher")
    parser.add_argument("--file", "-f", type=Path, required=True,
                       help="HL7 message file to publish (required)")
    parser.add_argument("--host", default="localhost",
                       help="Listener host")
    parser.add_argument("--port", type=int, default=2575,
                       help="Listener port")
    parser.add_argument("--schedule", "-s", type=int, metavar="SECONDS",
                       help="Publish on schedule (interval in seconds)")
    parser.add_argument("--count", "-c", type=int,
                       help="Number of messages to publish (with --schedule)")
    parser.add_argument("--retries", type=int, default=3,
                       help="Number of retry attempts")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Base delay between retries (seconds)")
    parser.add_argument("--timeout", type=int, default=10,
                       help="Connection timeout (seconds)")
    parser.add_argument("--audit-log", type=Path,
                       help="Path for audit log file (default: ./logs/publisher_audit.jsonl)")
    parser.add_argument("--no-audit", action="store_true",
                       help="Disable audit logging")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable INFO publisher logs")
    
    args = parser.parse_args()

    if not args.file.exists() or not args.file.is_file():
        parser.error(f"--file is required and must point to an existing file: {args.file}")

    if args.verbose:
        # Enable structured sender logs only when explicitly requested.
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(
            logging.Formatter(
                '{"timestamp": "%(asctime)s.%(msecs)03d", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        logger.handlers = [stream_handler]
        logger.setLevel(logging.INFO)

    audit_log_path = None
    if not args.no_audit:
        if args.audit_log:
            audit_log_path = args.audit_log
        else:
            audit_log_path = Path(__file__).parent.parent / "logs" / "publisher_audit.jsonl"
    
    publisher = HL7Publisher(
        host=args.host,
        port=args.port,
        retry_attempts=args.retries,
        retry_delay=args.delay,
        connection_timeout=args.timeout,
        audit_log_path=audit_log_path
    )

    try:
        if args.schedule:
            # Scheduled publishing mode
            print(f"Publishing messages every {args.schedule} seconds...")
            print("Press Ctrl+C to stop")
            publisher.publish_scheduled(args.file, args.schedule, args.count)
        else:
            # Single message mode
            with open(args.file) as f:
                message = f.read().replace('\n', '\r')

            print(f"Sending message from {args.file}...")
            success = publisher.send_message(message)

            if success:
                if publisher.last_ack_message:
                    print("Received ACK message:")
                    display_ack = publisher.last_ack_message.replace("\r", "\n").strip()
                    print(display_ack)
                sys.exit(0)
            else:
                if publisher.last_ack_message:
                    print("Received ACK message:")
                    display_ack = publisher.last_ack_message.replace("\r", "\n").strip()
                    print(display_ack)
                sys.exit(1)
    finally:
        if not args.no_audit and publisher.audit_log:
            publisher.save_audit_log()


if __name__ == "__main__":
    main()