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
- **JSON transformation layer:** 
- **FastAPI Backend:** Example REST API endpoint for receiving transformed HL7 messages.
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
│   │   └── config.py      # Configuration (not shown here)
│   ├── services/
│   │   └── transformer.py # HL7-to-JSON transformer
│   ├── api.py             # FastAPI REST API
│   ├── listener.py        # HL7 TCP/MLLP listener
│   └── sender.py          # HL7 sender client
├── examples/
│   └── sample_adt_a01.hl7 # Example HL7 message
└── README.md
```

---

## Requirements

- Python 3.8+
- [hl7apy](https://pypi.org/project/hl7apy/)
- [fastapi](https://fastapi.tiangolo.com/)
- [requests](https://pypi.org/project/requests/)
- [uvicorn](https://www.uvicorn.org/) (for running FastAPI)

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

### 1. Start the FastAPI Backend

```sh
uvicorn app.api:app --reload
```
Default: http://localhost:8000

### 2. Start the HL7 Listener

```sh
python3 -m app.listener
```
Expected output:
```sh
Listening on 0.0.0.0:2575
```

### 3. Send an HL7 Message

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

## MLLP Implementation

Messages are framed according to the MLLP standard:
- Start block: 0x0b
- End block: 0x1c0d
All inbound messages are validated for proper MLLP framing before parsing.

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
- Validation disabled (validation_level=0) to allow flexible HL7 parsing.
- ACK always returned, even on processing failure.
- Separation of concerns:
    - Framing logic isolated in mllp.py
    - ACK construction in ack.py
    - Transformation logic in transformer.py

## Limitations

- Single-message recv() (no streaming buffer management)
- No concurrency or async handling
- No TLS support
- Minimal HL7 segment coverage
- No persistence layer

---

## Future Improvements

- Add async or multi-threaded listener
- Add streaming buffer support
- Add message queue (e.g. Kafka)
- Add retry logic for API failures
- Add unit and integration tests
- Add Docker support
- Add structured logging

---

## License

MIT License

---

## References

- [HL7 Standard](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=185)
- [hl7apy Documentation](https://hl7apy.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)