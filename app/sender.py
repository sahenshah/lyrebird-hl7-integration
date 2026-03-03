import socket
from app.core.mllp import frame_message, deframe_message


def send_hl7(message, host="localhost", port=2575):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        sock.sendall(frame_message(message))

        ack = sock.recv(4096)
        try:
            ack_message = deframe_message(ack)
            print("Received ACK message:")
            for segment in ack_message.split('\r'):
                if segment:
                    print(segment)
        except Exception:
            print("Failed to deframe ACK:")
            print(ack)

if __name__ == "__main__":
    with open("examples/sample_adt_a01.hl7") as f:
        message = f.read().replace('\n', '\r')

    send_hl7(message)