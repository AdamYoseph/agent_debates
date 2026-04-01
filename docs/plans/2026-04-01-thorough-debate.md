# Thorough Debate & Consolidated Summary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make debates feel thorough by requiring agents to compare multiple named options, and produce a consolidated end-of-debate summary showing the winner and up to 10 runner-ups with brief reasons why each was not chosen.

**Architecture:** System prompt additions enforce multi-option research during debate. The FINAL_ANSWER format is extended with repeating `RUNNER_UP:` lines. The orchestrator merges both agents' runner-up lists, deduplicates, and prints the consolidated "Why not the others" section.

**Tech Stack:** Python 3, `re` (stdlib), existing `agent.py` / `orchestrator.py` / test files.

---

### Task 1: System prompt — enforce multi-option exploration

**Files:**
- Modify: `agent.py` (`build_system_prompt`)
- Modify: `tests/test_agent.py`

**Step 1: Write the failing test**

Add to `tests/test_agent.py`:

```python
def test_system_prompt_requires_multiple_options():
    prompt = build_system_prompt("Alpha")
    assert "3 specific options" in prompt or "at least 3" in prompt

def test_system_prompt_instructs_address_opponent_options():
    prompt = build_system_prompt("Alpha")
    assert "opponent" in prompt.lower() or "named options" in prompt.lower()
```

**Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_agent.py::test_system_prompt_requires_multiple_options tests/test_agent.py::test_system_prompt_instructs_address_opponent_options -v
```

Expected: FAIL — text not yet in prompt.

**Step 3: Update `build_system_prompt` in `agent.py`**

Add these two paragraphs after the `search_web` sentence and before the `RESPOND TO` paragraph:

```python
    return f"""You are a car-buying advisor named {name}. You are debating another advisor \
about the best car for the user's family. Take a dynamic position based on the conversation \
— let the arguments and evidence guide you, don't be assigned a fixed side.

You have access to a search_web tool. Use it to look up current car prices, insurance rates, \
reliability data, or any specific facts that would strengthen your argument.

Before advocating for a single option, identify and compare at least 3 specific options \
by name. Use search_web to gather concrete data on each — price, depreciation, and relevant \
specs. Name them explicitly so the debate stays grounded in real comparisons.

When responding to your opponent, address their specific named options directly \
(e.g. "you suggested X, but here is why Y is better") rather than arguing in the abstract.

When the context shows a "RESPOND TO [name]'s latest argument" section, address that person \
...
```

(Keep the rest of the prompt unchanged.)

**Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_agent.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: prompt agents to compare at least 3 named options before advocating"
```

---

### Task 2: Extend FINAL_ANSWER format and parser

**Files:**
- Modify: `agent.py` (`build_system_prompt` FINAL_ANSWER section, `parse_final_answer`)
- Modify: `tests/test_agent.py`

**Step 1: Write the failing tests**

Add to `tests/test_agent.py`:

```python
def test_parse_final_answer_with_runner_ups():
    response = """
RECOMMENDATION: Toyota RAV4 Hybrid
REASON: Best balance of reliability and running costs.
CONSENSUS: yes
RUNNER_UP: Kia Sorento — Higher insurance costs in Israel
RUNNER_UP: Skoda Kodiaq 2024 — Over budget when new
RUNNER_UP: Jaecoo J7 — Uncertain resale value
"""
    result = parse_final_answer(response)
    assert len(result["runner_ups"]) == 3
    assert result["runner_ups"][0]["name"] == "Kia Sorento"
    assert result["runner_ups"][0]["reason"] == "Higher insurance costs in Israel"


def test_parse_final_answer_no_runner_ups():
    response = """
RECOMMENDATION: Honda CR-V
REASON: Great reliability.
CONSENSUS: yes
"""
    result = parse_final_answer(response)
    assert result["runner_ups"] == []
```

**Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_agent.py::test_parse_final_answer_with_runner_ups tests/test_agent.py::test_parse_final_answer_no_runner_ups -v
```

Expected: FAIL — `runner_ups` key missing.

**Step 3: Update `parse_final_answer` in `agent.py`**

```python
def parse_final_answer(response: str) -> dict:
    rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response)
    reason_match = re.search(r"REASON:\s*(.+)", response)
    consensus_match = re.search(r"CONSENSUS:\s*(yes|no)", response, re.IGNORECASE)
    runner_up_matches = re.findall(r"RUNNER_UP:\s*(.+?)\s*—\s*(.+)", response)

    return {
        "recommendation": rec_match.group(1).strip() if rec_match else "",
        "reason": reason_match.group(1).strip() if reason_match else "",
        "consensus": (
            consensus_match.group(1).lower() == "yes" if consensus_match else False
        ),
        "runner_ups": [
            {"name": m[0].strip(), "reason": m[1].strip()} for m in runner_up_matches
        ],
    }
```

**Step 4: Update FINAL_ANSWER format in `build_system_prompt`**

Replace the FINAL_ANSWER block in the system prompt with:

```python
When the orchestrator sends signal FINAL_ANSWER, respond ONLY in this exact format:
RECOMMENDATION: <specific make/model/product>
REASON: <2-3 sentences explaining why>
CONSENSUS: yes/no
RUNNER_UP: <option name> — <one sentence why not chosen>
RUNNER_UP: <option name> — <one sentence why not chosen>
RUNNER_UP: <option name> — <one sentence why not chosen>
RUNNER_UP: <option name> — <one sentence why not chosen>
RUNNER_UP: <option name> — <one sentence why not chosen>
```

**Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_agent.py -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: extend FINAL_ANSWER format with RUNNER_UP lines and update parser"
```

---

### Task 3: Consolidated runner-up summary in orchestrator

**Files:**
- Modify: `orchestrator.py` (`format_final_results`)
- Modify: `tests/test_orchestrator.py`

**Step 1: Write the failing tests**

Add to `tests/test_orchestrator.py`:

```python
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
        "Alpha": {"recommendation": "Honda CR-V", "reason": "Great value.", "consensus": True},
        "Beta": {"recommendation": "Honda CR-V", "reason": "Reliable.", "consensus": True},
    }
    output = format_final_results(results)
    assert "Honda CR-V" in output
```

**Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_orchestrator.py::test_consolidated_runner_ups_shown tests/test_orchestrator.py::test_runner_ups_exclude_winner tests/test_orchestrator.py::test_no_runner_ups_section_when_empty tests/test_orchestrator.py::test_existing_tests_still_pass_without_runner_ups_key -v
```

Expected: FAIL.

**Step 3: Update `format_final_results` in `orchestrator.py`**

```python
def format_final_results(results: dict) -> str:
    all_agree = len(set(r["recommendation"] for r in results.values())) == 1 and all(
        r["consensus"] for r in results.values()
    )
    lines = ["\n" + "=" * 60, "FINAL RECOMMENDATIONS", "=" * 60]

    if all_agree:
        rec = list(results.values())[0]
        lines.append(f"\n✅ CONSENSUS REACHED: {rec['recommendation']}")
        lines.append(f"\nBoth agents agree: {rec['reason']}")
    else:
        lines.append("\n⚖️  No consensus — here are both picks:\n")
        for name, rec in results.items():
            lines.append(f"  {name}: {rec['recommendation']}")
            lines.append(f"    Reason: {rec['reason']}\n")
        lines.append("The final decision is yours!")

    # Consolidated runner-ups: merge, deduplicate, exclude winner(s), cap at 10
    winner_names = {r["recommendation"].lower() for r in results.values()}
    seen: set[str] = set()
    runner_ups: list[dict] = []
    for rec in results.values():
        for ru in rec.get("runner_ups", []):
            key = ru["name"].lower()
            if key not in seen and key not in winner_names:
                seen.add(key)
                runner_ups.append(ru)
            if len(runner_ups) >= 10:
                break
        if len(runner_ups) >= 10:
            break

    if runner_ups:
        lines.append("\nWhy not the others:")
        for ru in runner_ups:
            lines.append(f"  • {ru['name']} — {ru['reason']}")

    lines.append("=" * 60)
    return "\n".join(lines)
```

**Step 4: Run all tests**

```bash
python3 -m pytest -v
```

Expected: all 51+ tests pass.

**Step 5: Commit**

```bash
git add orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add consolidated runner-up summary to final results"
git push
```
