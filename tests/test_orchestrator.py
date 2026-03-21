# tests/test_orchestrator.py
import pytest
from orchestrator import format_final_results

def test_consensus_display():
    results = {
        "Alpha": {"recommendation": "Honda CR-V", "reason": "Great value.", "consensus": True},
        "Beta": {"recommendation": "Honda CR-V", "reason": "Reliable and roomy.", "consensus": True},
    }
    output = format_final_results(results)
    assert "CONSENSUS" in output
    assert "Honda CR-V" in output

def test_no_consensus_display():
    results = {
        "Alpha": {"recommendation": "Honda CR-V", "reason": "Great value.", "consensus": False},
        "Beta": {"recommendation": "Toyota RAV4", "reason": "Better AWD.", "consensus": False},
    }
    output = format_final_results(results)
    assert "Alpha" in output
    assert "Beta" in output
    assert "Honda CR-V" in output
    assert "Toyota RAV4" in output
