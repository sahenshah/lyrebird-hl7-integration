import logging

def transform_hl7_to_json(message):
    if not hasattr(message, "MSH") or not message.MSH:
        raise ValueError("Missing MSH segment")
    if not hasattr(message, "PID") or not message.PID:
        raise ValueError("Missing PID segment")

    msh = message.MSH
    pid = message.PID

    if not hasattr(msh, "MSH_10") or not msh.MSH_10 or not msh.MSH_10.to_er7():
        raise ValueError("Missing message control ID (MSH-10)")

    if not hasattr(pid, "PID_3") or not pid.PID_3 or not pid.PID_3.to_er7():
        raise ValueError("Missing patient MRN (PID-3)")

    if not hasattr(msh, "MSH_9") or not msh.MSH_9 or not msh.MSH_9.to_er7():
        raise ValueError("Missing message type (MSH-9)")

    patient_name = pid.PID_5.to_er7() if hasattr(pid, "PID_5") and pid.PID_5 else ""

    # Split PID_5 into last_name / first_name
    if "^" in patient_name:
        last_name, first_name = patient_name.split("^", 1)
    else:
        last_name, first_name = patient_name, ""

    return {
        "message_control_id": msh.MSH_10.to_er7(),
        "message_type": msh.MSH_9.to_er7(),
        "timestamp": msh.MSH_7.to_er7(),
        "patient": {
            "mrn": pid.PID_3.to_er7(),
            "first_name": first_name,
            "last_name": last_name,
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