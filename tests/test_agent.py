# tests/test_agent.py
from unittest.mock import MagicMock, patch

from agent import build_system_prompt, handle_tool_calls, parse_final_answer


def test_system_prompt_contains_name():
    prompt = build_system_prompt("Alpha")
    assert "Alpha" in prompt


def test_system_prompt_mentions_need_info():
    prompt = build_system_prompt("Beta")
    assert "NEED_INFO" in prompt


def test_system_prompt_mentions_final_answer():
    prompt = build_system_prompt("Alpha")
    assert "FINAL_ANSWER" in prompt


def test_parse_final_answer_consensus():
    response = """
RECOMMENDATION: Honda CR-V
REASON: Great reliability and space for families.
CONSENSUS: yes
"""
    result = parse_final_answer(response)
    assert result["recommendation"] == "Honda CR-V"
    assert result["consensus"] is True


def test_parse_final_answer_no_consensus():
    response = """
RECOMMENDATION: Toyota RAV4
REASON: Better off-road capability.
CONSENSUS: no
"""
    result = parse_final_answer(response)
    assert result["recommendation"] == "Toyota RAV4"
    assert result["consensus"] is False


def test_handle_tool_calls_no_function_calls():
    mock_response = MagicMock()
    mock_response.function_calls = []
    mock_response.text = "My final answer is the Toyota RAV4."
    mock_chat = MagicMock()

    result = handle_tool_calls(mock_response, mock_chat)

    assert result == "My final answer is the Toyota RAV4."
    mock_chat.send_message.assert_not_called()


def test_handle_tool_calls_executes_search():
    # First response: has a function call
    call = MagicMock()
    call.name = "search_web"
    call.args = {"query": "Toyota RAV4 price Israel"}

    first_response = MagicMock()
    first_response.function_calls = [call]

    # Second response: plain text
    second_response = MagicMock()
    second_response.function_calls = []
    second_response.text = "Based on research, the RAV4 costs $32k."

    mock_chat = MagicMock()
    mock_chat.send_message.return_value = second_response

    with patch("agent.search_web", return_value="RAV4 price: $32,000 | example.com"):
        result = handle_tool_calls(first_response, mock_chat)

    assert result == "Based on research, the RAV4 costs $32k."
    mock_chat.send_message.assert_called_once()


def test_system_prompt_requires_multiple_options():
    prompt = build_system_prompt("Alpha")
    assert "at least 3 specific options" in prompt


def test_system_prompt_instructs_address_opponent_options():
    prompt = build_system_prompt("Alpha")
    assert "named options directly" in prompt


def test_handle_tool_calls_caps_iterations():
    # Response always has a function call — should stop after MAX_TOOL_ITERATIONS
    call = MagicMock()
    call.name = "search_web"
    call.args = {"query": "test"}

    looping_response = MagicMock()
    looping_response.function_calls = [call]
    looping_response.text = "partial"

    mock_chat = MagicMock()
    mock_chat.send_message.return_value = looping_response

    with patch("agent.search_web", return_value="result"):
        result = handle_tool_calls(looping_response, mock_chat)

    assert mock_chat.send_message.call_count <= 5
    assert result == "partial"
