# socket_utils.py
import socket
import struct
from protocol import Message


def send_message(sock: socket.socket, msg: Message) -> None:
    """Send a length-prefixed JSON message."""
    data = msg.to_json().encode("utf-8")
    length = struct.pack(">I", len(data))
    sock.sendall(length + data)


def recv_message(sock: socket.socket) -> Message:
    """Receive a length-prefixed JSON message."""
    raw_length = _recv_exact(sock, 4)
    length = struct.unpack(">I", raw_length)[0]
    raw_data = _recv_exact(sock, length)
    return Message.from_json(raw_data.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed unexpectedly")
        data += chunk
    return data
