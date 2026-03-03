"""
This verifies:

- Correct control ID
- Correct sender/receiver swap
- Proper ACK code
"""

from hl7apy.parser import parse_message
from app.core.ack import build_ack


def test_ack_swaps_sender_and_receiver():
    hl7 = (
        "MSH|^~\\&|SendApp|SendFac|RecvApp|RecvFac|20260302||ADT^A01|123456|P|2.3\r"
        "PID|1||MRN123||Doe^John\r"
    )

    parsed = parse_message(hl7)
    ack = build_ack(parsed, "AA")

    assert "MSA|AA|123456" in ack
    assert "RecvApp|RecvFac|SendApp|SendFac" in ack