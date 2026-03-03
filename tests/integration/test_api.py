import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.services.transformer import transform_hl7_to_json
from hl7apy.parser import parse_message

client = TestClient(app)

SAMPLE_HL7 = (
    "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260303||ADT^A01|123456|P|2.3\r"
    "PID|1||MRN12345||Doe^John||19900101|M\r"
)

@pytest.fixture
def transformed_payload():
    parsed = parse_message(SAMPLE_HL7)
    return transform_hl7_to_json(parsed)

def test_api_accepts_full_payload(transformed_payload):
    """
    Test that the API accepts a fully valid HL7-transformed payload and returns a 200 OK
    with a status of 'received'.
    """
    response = client.post("/api/v1/messages", json=transformed_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"

def test_api_rejects_missing_patient_mrn(transformed_payload):
    """
    Test that the API rejects a payload missing the patient MRN, returning a 400 error
    and an appropriate error message.
    """
    # Remove patient MRN
    transformed_payload["patient"]["mrn"] = ""
    response = client.post("/api/v1/messages", json=transformed_payload)
    assert response.status_code == 400
    assert "Missing patient MRN" in response.json()["detail"]

def test_api_accepts_missing_source(transformed_payload):
    """
    Test that the API accepts a payload even if the optional 'source' field is missing,
    and still returns a 200 OK.
    """
    # Remove source
    del transformed_payload["source"]
    response = client.post("/api/v1/messages", json=transformed_payload)
    assert response.status_code == 200