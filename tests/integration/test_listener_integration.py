import json
import socket
import time
from pathlib import Path

import pytest
import requests
from hl7apy.parser import parse_message

from app.core.config import (
    HL7_HOST,
    HL7_PORT,
    API_URL,
    DOWNSTREAM_API_URL,
    DOWNSTREAM_CA_BUNDLE,
)
from app.core.mllp import frame_message
from app.services.transformer import transform_hl7_to_json

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def integration_stack(start_stub_api, start_backend, start_listener):
    """
    Starts required services from conftest.py:
    - downstream API
    - FastAPI backend
    - HL7 listener
    """
    yield


def _listener_addr() -> tuple[str, int]:
    host = "127.0.0.1" if HL7_HOST in {"0.0.0.0", "::"} else HL7_HOST
    return host, HL7_PORT


def _resolve_ca_bundle() -> str:
    candidates = []
    if DOWNSTREAM_CA_BUNDLE:
        p = Path(DOWNSTREAM_CA_BUNDLE)
        candidates.append(p)
        if str(p).startswith("/certs/"):
            candidates.append(_REPO_ROOT / str(p).lstrip("/"))
    candidates.append(_REPO_ROOT / "certs" / "stub.crt")

    for c in candidates:
        if c.exists():
            return str(c)
    raise RuntimeError("No valid CA bundle found for downstream API.")


STUB_CA_BUNDLE = _resolve_ca_bundle()


def _send_hl7_and_get_ack(hl7: str) -> bytes:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(_listener_addr())
        s.sendall(frame_message(hl7))
        return s.recv(4096)


def test_listener_processes_good_message_and_sends_ack():
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260309||ADT^A01|GOOD001|P|2.3\r"
        "PID|1||MRN999||Doe^Jane||19920101|F\r"
    )
    ack = _send_hl7_and_get_ack(hl7)
    assert b"MSA|AA|GOOD001" in ack


def test_fastapi_and_downstream_receive_expected_json_shape():
    """
    Verifies:
    1) FastAPI accepts transformed payload.
    2) Downstream /receive endpoint accepts the same payload shape.

    Note: with only /receive available, there is no observability endpoint to fetch
    'what was forwarded', so this validates contract compatibility end-to-end.
    """
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260309||ADT^A01|JSON001|P|2.3\r"
        "PID|1||MRN123||Doe^John||19900101|M\r"
    )
    payload = transform_hl7_to_json(parse_message(hl7))

    # FastAPI accepts payload
    api_resp = requests.post(API_URL.rstrip("/"), json=payload, timeout=10)
    api_resp.raise_for_status()

    # Downstream accepts same payload at the only allowed endpoint: /receive
    ds_resp = requests.post(
        DOWNSTREAM_API_URL.rstrip("/"),
        json=payload,
        timeout=10,
        verify=STUB_CA_BUNDLE,
    )
    ds_resp.raise_for_status()

    # Minimal payload correctness assertion
    assert payload["message_control_id"] == "JSON001"
    assert payload["patient"]["mrn"] == "MRN123"

    # Small delay to reduce race conditions in CI logs/output ordering
    time.sleep(0.1)