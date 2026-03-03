import logging
from hl7apy.parser import parse_message

def transform_hl7_to_json(message) -> dict:
    try:
        pid = message.PID
        patient_id = getattr(pid.PID_3, "to_er7", lambda: getattr(pid.PID_3, "value", ""))() if hasattr(pid, "PID_3") else ""
        first_name = getattr(pid.PID_5.PID_5_2, "to_er7", lambda: getattr(pid.PID_5.PID_5_2, "value", ""))() if hasattr(pid, "PID_5") and hasattr(pid.PID_5, "PID_5_2") else ""
        last_name = getattr(pid.PID_5.PID_5_1, "to_er7", lambda: getattr(pid.PID_5.PID_5_1, "value", ""))() if hasattr(pid, "PID_5") and hasattr(pid.PID_5, "PID_5_1") else ""
        dob = getattr(pid.PID_7, "to_er7", lambda: getattr(pid.PID_7, "value", ""))() if hasattr(pid, "PID_7") else ""
        gender = getattr(pid.PID_8, "to_er7", lambda: getattr(pid.PID_8, "value", ""))() if hasattr(pid, "PID_8") else ""
        logging.debug(f"Extracted patient_id: {patient_id}, first_name: {first_name}, last_name: {last_name}, dob: {dob}, gender: {gender}")
    except Exception as e:
        logging.error(f"Failed to extract patient fields: {e}")
        raise

    return {
        "message_type": message.MSH.MSH_9.to_er7() if hasattr(message.MSH, "MSH_9") else "",
        "message_control_id": message.MSH.MSH_10.to_er7() if hasattr(message.MSH, "MSH_10") else "",
        "patient": {
            "id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "gender": gender,
        },
    }