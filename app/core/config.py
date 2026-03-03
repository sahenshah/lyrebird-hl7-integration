import os
from dotenv import load_dotenv
load_dotenv()

HL7_HOST = os.getenv("HL7_HOST", "0.0.0.0")
HL7_PORT = int(os.getenv("HL7_PORT", 2575))
API_URL = os.getenv("API_URL", "http://localhost:8080/api/v1/messages")
BUFFER_SIZE_LIMIT = int(os.getenv("BUFFER_SIZE_LIMIT", 1048576))
MAX_FRAMING_ERRORS = int(os.getenv("MAX_FRAMING_ERRORS", 5))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", 0.5))
IDEMPOTENCY_CACHE_SIZE = int(os.getenv("IDEMPOTENCY_CACHE_SIZE", 1000))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 5))