from datetime import datetime


def build_ack(original_message, ack_code="AA"):
    msh = original_message.MSH
    # Swap sending and receiving fields for the ACK
    sending_app = msh.MSH_5.to_er7()   # ReceivingApp from original
    sending_fac = msh.MSH_6.to_er7()   # ReceivingFacility from original
    receiving_app = msh.MSH_3.to_er7() # SendingApp from original
    receiving_fac = msh.MSH_4.to_er7() # SendingFacility from original
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    original_control_id = msh.MSH_10.to_er7()
    version = msh.MSH_12.to_er7() if hasattr(msh, "MSH_12") else "2.5"

    ack = (
        f"MSH|^~\\&|{sending_app}|{sending_fac}|{receiving_app}|{receiving_fac}|"
        f"{timestamp}||ACK|{original_control_id}|P|{version}\r"
        f"MSA|{ack_code}|{original_control_id}\r"
    )
    return ack