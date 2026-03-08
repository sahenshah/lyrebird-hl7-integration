from datetime import datetime, timezone
import uuid


def safe_get(component, default=""):
    """
    Safely extract ER7 value from an HL7 field component.
    """
    try:
        return component.to_er7()
    except Exception:
        return default


def build_ack(original_message, ack_code="AA"):
    """
    Build an HL7 ACK message (ER7 string) in response to an original message.

    Returns:
        str: ER7-formatted ACK message
    """

    try:
        msh = original_message.MSH
    except Exception:
        # If original message is completely unusable,
        # return minimal fallback ACK
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return (
            f"MSH|^~\\&|||||{timestamp}||ACK|{uuid.uuid4()}|P|2.5\r"
            f"MSA|AE|\r"
        )

    # Swap sending and receiving fields
    sending_app = safe_get(msh.MSH_5)
    sending_fac = safe_get(msh.MSH_6)
    receiving_app = safe_get(msh.MSH_3)
    receiving_fac = safe_get(msh.MSH_4)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    original_control_id = safe_get(msh.MSH_10)
    version = safe_get(msh.MSH_12, default="2.5")

    # Generate new ACK message control ID (recommended best practice)
    ack_control_id = str(uuid.uuid4())

    ack_message = (
        f"MSH|^~\\&|{sending_app}|{sending_fac}|"
        f"{receiving_app}|{receiving_fac}|"
        f"{timestamp}||ACK|{ack_control_id}|P|{version}\r"
        f"MSA|{ack_code}|{original_control_id}\r"
    )

    return ack_message