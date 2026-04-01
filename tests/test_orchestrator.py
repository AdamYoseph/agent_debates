# tests/test_orchestrator.py
from orchestrator import format_final_results


def test_consensus_display():
    results = {
        "Alpha": {
            "recommendation": "Honda CR-V",
            "reason": "Great value.",
            "consensus": True,
        },
        "Beta": {
            "recommendation": "Honda CR-V",
            "reason": "Reliable and roomy.",
            "consensus": True,
        },
    }
    output = format_final_results(results)
    assert "CONSENSUS" in output
    assert "Honda CR-V" in output


def test_no_consensus_display():
    results = {
        "Alpha": {
            "recommendation": "Honda CR-V",
            "reason": "Great value.",
            "consensus": False,
        },
        "Beta": {
            "recommendation": "Toyota RAV4",
            "reason": "Better AWD.",
            "consensus": False,
        },
    }
    output = format_final_results(results)
    assert "Alpha" in output
    assert "Beta" in output
    assert "Honda CR-V" in output
    assert "Toyota RAV4" in output


def test_consolidated_runner_ups_shown():
    results = {
        "Alpha": {
            "recommendation": "Toyota RAV4",
            "reason": "Best reliability.",
            "consensus": True,
            "runner_ups": [
                {"name": "Kia Sorento", "reason": "Higher insurance"},
                {"name": "Honda CR-V", "reason": "Less cargo space"},
            ],
        },
        "Beta": {
            "recommendation": "Toyota RAV4",
            "reason": "Best resale value.",
            "consensus": True,
            "runner_ups": [
                {"name": "Kia Sorento", "reason": "Worse depreciation"},
                {"name": "Skoda Kodiaq", "reason": "Over budget"},
            ],
        },
    }
    output = format_final_results(results)
    assert "Why not the others" in output
    assert "Kia Sorento" in output
    assert output.count("Kia Sorento") == 1  # deduped
    assert "Honda CR-V" in output
    assert "Skoda Kodiaq" in output


def test_runner_ups_exclude_winner():
    results = {
        "Alpha": {
            "recommendation": "Toyota RAV4",
            "reason": "Best reliability.",
            "consensus": True,
            "runner_ups": [
                {"name": "Toyota RAV4", "reason": "Reconsidered"},
                {"name": "Honda CR-V", "reason": "Less space"},
            ],
        },
        "Beta": {
            "recommendation": "Toyota RAV4",
            "reason": "Best value.",
            "consensus": True,
            "runner_ups": [],
        },
    }
    output = format_final_results(results)
    after_runner_ups = output.split("Why not the others")[-1]
    assert "Toyota RAV4" not in after_runner_ups


def test_no_runner_ups_section_when_empty():
    results = {
        "Alpha": {
            "recommendation": "Honda CR-V",
            "reason": "Great value.",
            "consensus": True,
            "runner_ups": [],
        },
        "Beta": {
            "recommendation": "Honda CR-V",
            "reason": "Reliable.",
            "consensus": True,
            "runner_ups": [],
        },
    }
    output = format_final_results(results)
    assert "Why not the others" not in output


def test_existing_tests_still_pass_without_runner_ups_key():
    # format_final_results must handle results dicts that lack the runner_ups key
    results = {
        "Alpha": {
            "recommendation": "Honda CR-V",
            "reason": "Great value.",
            "consensus": True,
        },
        "Beta": {
            "recommendation": "Honda CR-V",
            "reason": "Reliable.",
            "consensus": True,
        },
    }
    output = format_final_results(results)
    assert "Honda CR-V" in output


def test_runner_ups_capped_at_ten():
    # Supply 15 unique runner-ups across two agents; only 10 should appear
    alpha_runners = [
        {"name": f"Option {i}", "reason": f"Reason {i}"} for i in range(1, 11)
    ]
    beta_runners = [
        {"name": f"Option {i}", "reason": f"Reason {i}"} for i in range(11, 16)
    ]
    results = {
        "Alpha": {
            "recommendation": "Winner",
            "reason": "Best.",
            "consensus": True,
            "runner_ups": alpha_runners,
        },
        "Beta": {
            "recommendation": "Winner",
            "reason": "Best.",
            "consensus": True,
            "runner_ups": beta_runners,
        },
    }
    output = format_final_results(results)
    assert output.count("•") == 10
