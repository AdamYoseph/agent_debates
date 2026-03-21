# tests/test_socket_utils.py
import socket
import threading
import json
import pytest
from socket_utils import send_message, recv_message
from protocol import Message

def test_send_and_recv():
    """Round-trip a message through a real socket pair."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("localhost", 65499))
    server_sock.listen(1)

    received = []

    def server():
        conn, _ = server_sock.accept()
        msg = recv_message(conn)
        received.append(msg)
        conn.close()
        server_sock.close()

    t = threading.Thread(target=server)
    t.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("localhost", 65499))
    msg = Message(role="agent", name="Alpha", content="Test content", signal=None)
    send_message(client, msg)
    client.close()

    t.join(timeout=3)
    assert len(received) == 1
    assert received[0].content == "Test content"
    assert received[0].name == "Alpha"
