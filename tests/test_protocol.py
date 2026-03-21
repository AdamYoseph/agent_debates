# tests/test_protocol.py
import json
import pytest
from protocol import Message, Signal

def test_message_serialization():
    msg = Message(role="agent", name="Alpha", content="Hello", signal=None)
    data = msg.to_json()
    parsed = json.loads(data)
    assert parsed["role"] == "agent"
    assert parsed["name"] == "Alpha"
    assert parsed["content"] == "Hello"
    assert parsed["signal"] is None

def test_message_deserialization():
    raw = json.dumps({"role": "orchestrator", "name": "Orchestrator", "content": "Go", "signal": "FINAL_ANSWER"})
    msg = Message.from_json(raw)
    assert msg.signal == Signal.FINAL_ANSWER

def test_need_info_signal():
    assert Signal.NEED_INFO == "NEED_INFO"

def test_final_answer_signal():
    assert Signal.FINAL_ANSWER == "FINAL_ANSWER"

def test_message_from_json_no_signal():
    raw = json.dumps({"role": "agent", "name": "Beta", "content": "My argument", "signal": None})
    msg = Message.from_json(raw)
    assert msg.signal is None
