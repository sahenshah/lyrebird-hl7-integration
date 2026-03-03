import logging
from hl7apy.parser import parse_message

def transform_hl7_to_json(message):
    msh = message.MSH
    pid = message.PID

    if not hasattr(message, "PID") or not message.PID: 
        raise ValueError("Missing PID segment")

    return {
        "control_id": msh.MSH_10.to_er7(),
        "message_type": msh.MSH_9.to_er7(),
        "timestamp": msh.MSH_7.to_er7(),
        "patient": {
            "id": pid.PID_3.to_er7(),
            "name": pid.PID_5.to_er7(),
            "dob": pid.PID_7.to_er7(),
            "sex": pid.PID_8.to_er7(),
        },
        "source": {
            "sending_app": msh.MSH_3.to_er7(),
            "sending_facility": msh.MSH_4.to_er7(),
        },
    }

def normalize_hl7_segments(message: str) -> str:
    # Replace CRLF and LF with CR
    return message.replace('\r\n', '\r').replace('\n', '\r')