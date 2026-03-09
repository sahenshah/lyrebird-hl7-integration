"""
This test verifies:

- HL7 to JSON transformation raises an exception when required PID segment is missing.
- HL7 to JSON transformation raises an exception when MSH-10 (Message Control ID) is missing.
"""

import pytest
from hl7apy.parser import parse_message
from app.services.transformer import transform_hl7_to_json


def test_missing_pid_raises():
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01|123456|P|2.3\r"
    )

    parsed = parse_message(hl7)

    with pytest.raises(Exception):
        transform_hl7_to_json(parsed)


def test_missing_message_control_id_raises():
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01||P|2.3\r"
        "PID|||12345||Doe^John\r"
    )

    parsed = parse_message(hl7)

    with pytest.raises(Exception):
        transform_hl7_to_json(parsed)