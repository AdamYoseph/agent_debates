# tests/test_agent.py
import pytest
from agent import build_system_prompt, parse_final_answer

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
