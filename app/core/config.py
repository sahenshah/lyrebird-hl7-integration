import os

HOST = os.getenv("HL7_HOST", "0.0.0.0")
PORT = int(os.getenv("HL7_PORT", 2575))

API_URL = os.getenv("API_URL", "http://localhost:8080/api/v1/messages")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 5))