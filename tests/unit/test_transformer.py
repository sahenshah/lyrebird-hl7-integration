"""
This test verifies:

- HL7 to JSON transformation extracts correct control ID
- Patient ID is correctly parsed from PID segment
- Message type is correctly extracted from MSH segment
"""

from hl7apy.parser import parse_message
from app.services.transformer import transform_hl7_to_json


def test_transform_valid_message():
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01|123456|P|2.3\r"
        "PID|1||MRN123||Doe^John||19900101|M\r"
    )

    parsed = parse_message(hl7)
    result = transform_hl7_to_json(parsed)

    assert result["message_control_id"] == "123456"
    assert result["patient"]["mrn"] == "MRN123"
    assert result["patient"]["first_name"] == "John"
    assert result["patient"]["last_name"] == "Doe"
    assert result["patient"]["dob"] == "19900101"
    assert result["patient"]["sex"] == "M"
    assert result["message_type"] == "ADT^A01"