# Lyrebird HL7 Integration

This project implements a minimal HL7 v2.x integration service using TCP/MLLP. It receives HL7 messages, parses them, transforms them into JSON, forwards them to a REST API, and returns a standards-compliant HL7 ACK/NACK response.

The goal is to demonstrate core healthcare integration concepts including:
- HL7 v2 message handling
- MLLP framing over TCP
- ACK/NACK generation
- Message transformation
- Downstream API forwarding

---

## Architecture Overview

```sh
HL7 Sender
    │
    ▼
MLLP TCP Listener
    │
    ▼
HL7 Parser (hl7apy)
    │
    ▼
HL7 → JSON Transformer
    │
    ▼
FastAPI Backend (REST)
    │
    ▼
HL7 ACK returned to Sender
```

**Flow Summary**
1. Listener accepts TCP connection.
2. Message is deframed using MLLP.
3. HL7 message is parsed using hl7apy.
4. Parsed message is transformed into JSON.
5. JSON is POSTed to a FastAPI endpoint.
6. Listener returns:
    - AA (Application Accept) on success
    - AE (Application Error) on failure

---

## Features

- **HL7 Listener:** Receives HL7 messages over TCP/MLLP, parses them, transforms to JSON, and forwards to a REST API.
- **HL7 Sender:** Sends HL7 messages to the listener and prints the received ACK.
- **HL7 Parsing:** Uses [hl7apy](https://github.com/crs4/hl7apy) for robust HL7 v2.x parsing.
- **MLLP Framing:** Implements MLLP framing/deframing for HL7 over TCP.
- **Robust Buffering:** Handles partial and multiple HL7 messages per TCP packet, waiting for complete MLLP frames before processing.
- **Buffer Size & Framing Error Limits:** Enforces a buffer size limit (default: 1 MB) and limits repeated framing errors (default: 5) to prevent memory exhaustion or protocol abuse.
- **JSON transformation layer:** 
- **FastAPI Backend:** Example REST API endpoint for receiving transformed HL7 messages.
- **Health Endpoint:** `/health` endpoint for readiness and monitoring.
- **Robust ACK Handling:** Generates HL7-compliant ACK/NACK messages.
- **Error handling and logging**

---

## Project Structure

```
lyrebird-hl7-integration/
├── app/
│   ├── core/
│   │   ├── ack.py         # HL7 ACK message builder
│   │   ├── mllp.py        # MLLP framing/deframing utilities
│   │   └── config.py      # Configuration (loads from .env)
│   ├── services/
│   │   └── transformer.py # HL7-to-JSON transformer
│   ├── api.py             # FastAPI REST API
│   ├── listener.py        # HL7 TCP/MLLP listener
│   └── sender.py          # HL7 sender client
├── examples/
│   └── sample_adt_a01.hl7 # Example HL7 message
├── .env                   # Environment configuration
└── README.md
```

---

## Requirements

- Python 3.8+
- [hl7apy](https://pypi.org/project/hl7apy/)
- [fastapi](https://fastapi.tiangolo.com/)
- [requests](https://pypi.org/project/requests/)
- [uvicorn](https://www.uvicorn.org/) (for running FastAPI)
- [python-dotenv](https://pypi.org/project/python-dotenv/) (for .env support)

Install dependencies:

```sh
pip install -r requirements.txt
```

**HL7 Version Notes**
This implementation uses hl7apy 1.3.5.
- Parsing is performed with validation_level=0 to allow flexible message handling.
- Supported HL7 versions (e.g. 2.3.1, 2.5, 2.6) should be used in MSH-12.
- Messages are expected to follow HL7 v2.x formatting conventions.

---

## Usage

### 1. Configure Environment

Add a `.env` file in your project root to override default settings:

```
HL7_HOST=0.0.0.0
HL7_PORT=2575
API_URL=http://localhost:8080/api/v1/messages
BUFFER_SIZE_LIMIT=1048576
MAX_FRAMING_ERRORS=5
MAX_RETRIES=3
RETRY_BACKOFF_BASE=0.5
IDEMPOTENCY_CACHE_SIZE=1000
API_TIMEOUT=5
```

### 2. Start the FastAPI Backend

```sh
uvicorn app.api:app --reload
```
Default: http://localhost:8000

#### Health Check Endpoint

To verify the API is running and ready for monitoring, use:

```sh
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### 3. Start the HL7 Listener

```sh
python3 -m app.listener
```
Expected output:
```sh
Listening on 0.0.0.0:2575
```

### 4. Send an HL7 Message

```sh
python3 -m app.sender
```

Expected sender output:

```sh
Received ACK message:
MSH|...
MSA|AA|123456
```

---

## Example HL7 Message

Located at `examples/sample_adt_a01.hl7`:

```
MSH|^~\&|SendingApp|SendingFacility|ReceivingApp|ReceivingFacility|202603021200||ADT^A01|123456|P|2.3
PID|1||MRN12345||Doe^John||19900101|M|||123 Main St^^City^ST^12345||555-1234
```
Segments must be separated by carriage return (\r).
MLLP framing is applied automatically by the sender.

---

## Example JSON Output 

Example transformed payload:

```
{
  "message_type": "ADT^A01",
  "message_control_id": "123456",
  "patient": {
    "mrn": "MRN12345",
    "first_name": "John",
    "last_name": "Doe",
    "dob": "19900101",
    "sex": "M"
  }
}
```

---

## 🧪 Testing

### How to Run the Tests

All tests are located in the `tests/` directory. To run the full suite:

```sh
pytest
```
or
```sh
pytest -v
```

### Test Types

- **Unit Tests:** Validate individual components (MLLP framing, HL7 parsing, transformation, ACK logic).
- **Integration Tests:** Simulate a real HL7 sender connecting over TCP, sending a message, and receiving an ACK or NACK.

### Example: Integration Test

The integration test (`test_listener_integration.py`) demonstrates a full roundtrip:
- Starts the HL7 listener on a custom host/port in a background thread.
- Sends a framed HL7 message over TCP.
- Verifies that an HL7 ACK is returned.
- Mocks the API call to isolate listener behavior.
- Also tests error scenarios such as invalid HL7 and downstream API failures.

---

## Test Coverage Highlights

| Area                       | Test(s)                                              | What’s Verified                                                                 |
|----------------------------|------------------------------------------------------|---------------------------------------------------------------------------------|
| **MLLP framing/deframing** | `test_frame_and_deframe_roundtrip`<br>`test_extract_multiple_messages` | Correct wrapping/unwrapping and handling of multiple messages per TCP packet     |
| **ACK correctness**        | `test_ack_swaps_sender_and_receiver`                 | Proper MSH sender/receiver swap and ACK code                                    |
| **HL7 → JSON transformer** | `test_transform_valid_message`                       | Extraction of control ID, patient ID, and other key fields                      |
| **Error handling**         | `test_missing_pid_raises`                            | Missing critical segments trigger exceptions or NACKs                            |
| **Integration**            | `test_listener_returns_ack`                          | End-to-end: sender → listener → API → ACK                                        |
| **Invalid HL7 structure**  | `test_listener_returns_ae_for_invalid_hl7`           | Malformed HL7 message triggers AE ACK response                                   |
| **API failure handling**   | `test_listener_returns_ae_when_api_fails`            | Simulated API failure triggers AE ACK response                                   |
| **API payload validation** | `test_listener_sends_expected_json`                  | Listener sends correct JSON payload to API when receiving a valid HL7 message    |
| **API retry logic**        | `test_send_to_api_retries_and_succeeds`<br>`test_send_to_api_retries_configured_times` | Ensures `send_to_api` retries on transient network errors and respects the configured retry count |
| **API contract**           | `test_api_accepts_full_payload`<br>`test_api_rejects_missing_patient_mrn`<br>`test_api_accepts_missing_source` | API endpoint accepts valid payloads, rejects invalid ones, and handles optional fields |

---

## Production Hardening Roadmap

The current test suite validates correctness and core integration behavior.
The following extensions would further harden the system for real clinical deployments: 
- **Partial messages:** Simulate TCP packets with incomplete MLLP frames to test buffering logic.
- **Multiple back-to-back messages:** Test with 3–5 messages in one buffer to catch iteration bugs.
- **Invalid HL7 structures:** Handle wrong segment separators, missing MSH, or unknown message types (expect AE NACKs).
- **API failures:** Simulate API errors (500, timeouts, network issues) and verify retry/NACK logic.
- **Large messages:** Stress test with large HL7 messages (0.5–1 MB) to check buffer/memory handling.
- **Edge HL7 fields:** Test PID with multiple identifiers, missing optional fields, or uncommon encodings.
- **Concurrency / multi-connection:** If threading is added, simulate multiple simultaneous HL7 connections.

---

*See `tests/` for implementation details and expand as needed for your use case!*

---

## MLLP Implementation

Messages are framed according to the MLLP standard:
- Start block: 0x0b
- End block: 0x1c0d
All inbound messages are validated for proper MLLP framing before parsing.

**Robustness Notes:**
- The listener accumulates incoming data in a buffer and only processes messages when a full MLLP frame is present.
- Handles multiple and partial HL7 messages per TCP packet.
- If the buffer exceeds 1 MB or repeated framing errors (default: 5) are detected, the buffer is cleared and the connection is closed to prevent memory exhaustion or protocol abuse.

---

## Error Handling

- Invalid MLLP framing → returns AE
- Parsing failure → returns AE
- API failure → returns AE
- Successful processing → returns AA

Errors are logged for observability.

---

## Design Decisions

- Single-threaded listener for simplicity and clarity.
- Streaming buffer management: supports partial and multiple HL7 messages per TCP packet.
- Validation disabled (validation_level=0) to allow flexible HL7 parsing.
- ACK always returned, even on processing failure.
- Separation of concerns:
    - Framing logic isolated in mllp.py
    - ACK construction in ack.py
    - Transformation logic in transformer.py

## Limitations

- No concurrency or async handling
- No TLS support
- Minimal HL7 segment coverage
- No persistence layer

---

## Future Improvements

- Add async or multi-threaded listener
- Add message queue (e.g. Kafka)
- Add retry logic for API failures
- Add unit and integration tests
- Add Docker support
- Add structured logging

---
