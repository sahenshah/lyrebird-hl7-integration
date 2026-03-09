import os
from dotenv import load_dotenv
load_dotenv()

HL7_HOST = os.getenv("HL7_HOST", "0.0.0.0")
HL7_PORT = int(os.getenv("HL7_PORT", 2575))
API_BIND_HOST = os.getenv("API_BIND_HOST", "0.0.0.0")
API_BIND_PORT = int(os.getenv("API_BIND_PORT", 8000))
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1/messages")
API_CA_BUNDLE = os.path.expanduser(os.getenv("API_CA_BUNDLE", "")).strip() or None
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 5))
BUFFER_SIZE_LIMIT = int(os.getenv("BUFFER_SIZE_LIMIT", 1048576))
MAX_FRAMING_ERRORS = int(os.getenv("MAX_FRAMING_ERRORS", 5))
MAX_BUFFER_SIZE = int(os.getenv("MAX_BUFFER_SIZE", 1048576))
MAX_MESSAGE_SIZE = int(os.getenv("MAX_MESSAGE_SIZE", 1048576))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", 0.5))
IDEMPOTENCY_CACHE_SIZE = int(os.getenv("IDEMPOTENCY_CACHE_SIZE", 1000))
_idempotency_ttl_seconds = os.getenv("IDEMPOTENCY_TTL_SECONDS")
_idempotency_expiry_hours = os.getenv("IDEMPOTENCY_EXPIRY_HOURS")
if _idempotency_ttl_seconds is not None:
    IDEMPOTENCY_TTL_SECONDS = int(_idempotency_ttl_seconds)
elif _idempotency_expiry_hours is not None:
    IDEMPOTENCY_TTL_SECONDS = int(_idempotency_expiry_hours) * 3600
else:
    IDEMPOTENCY_TTL_SECONDS = 86400

IDEMPOTENCY_MAXSIZE = int(os.getenv("IDEMPOTENCY_MAXSIZE", IDEMPOTENCY_CACHE_SIZE))
DOWNSTREAM_CA_BUNDLE = os.path.expanduser(os.getenv("DOWNSTREAM_CA_BUNDLE","~/lyrebird-hl7-integration/certs/stub.crt"))
DOWNSTREAM_API_PORT = int(os.getenv("DOWNSTREAM_API_PORT", 9000))
DOWNSTREAM_API_HOST = os.getenv("DOWNSTREAM_API_HOST", "localhost")
DOWNSTREAM_API_URL = os.getenv("DOWNSTREAM_API_URL", "https://localhost:9000/receive")