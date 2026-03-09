"""
Edge markers: @pytest.mark.edge allows you to run only edge-case tests with:

    pytest -m edge
"""
from copy import deepcopy

import requests
from hl7apy.parser import parse_message

from app.core.config import API_URL
from app.services.transformer import transform_hl7_to_json

SAMPLE_HL7 = (
    "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260303||ADT^A01|123456|P|2.3\r"
    "PID|1||MRN12345||Doe^John||19900101|M\r"
)


def transformed_payload():
    parsed = parse_message(SAMPLE_HL7)
    return transform_hl7_to_json(parsed)


def _messages_url() -> str:
    return API_URL.rstrip("/")


def test_api_accepts_full_payload():
    payload = transformed_payload()
    response = requests.post(_messages_url(), json=payload, timeout=10)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"


def test_api_rejects_missing_patient_mrn():
    payload = deepcopy(transformed_payload())
    payload["patient"]["mrn"] = ""
    response = requests.post(_messages_url(), json=payload, timeout=10)
    assert response.status_code == 400
    assert "Missing patient MRN" in response.json()["detail"]


def test_api_accepts_missing_source():
    payload = deepcopy(transformed_payload())
    payload.pop("source", None)
    response = requests.post(_messages_url(), json=payload, timeout=10)
    assert response.status_code == 200