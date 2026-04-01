# Thorough Debate & Consolidated Summary

**Date:** 2026-04-01
**Status:** Approved

## Goal

Make debates feel thorough by requiring agents to explicitly compare multiple named options, and produce a consolidated end-of-debate summary showing the winner and up to 10 runner-ups with brief reasons why each was not chosen.

## Approach

Approach A — system prompt update + extended FINAL_ANSWER format + orchestrator summary formatter. No new signals, phases, or data structures.

## Section 1: System Prompt — Enforcing Thoroughness

Two additions to `build_system_prompt` in `agent.py`:

1. Agents must identify and compare at least 3 specific options by name before advocating for one, using `search_web` to gather concrete data (price, depreciation, specs) on each.
2. When responding to the opponent, agents must address the opponent's specific named options directly ("you suggested X, but here's why Y is better") rather than arguing in the abstract.

## Section 2: Extended FINAL_ANSWER Format

System prompt FINAL_ANSWER format updated to require repeating `RUNNER_UP:` lines (up to 5 per agent):

```
RECOMMENDATION: <specific option>
REASON: <2-3 sentences>
CONSENSUS: yes/no
RUNNER_UP: <option name> — <one sentence why not chosen>
RUNNER_UP: <option name> — <one sentence why not chosen>
...
```

`parse_final_answer` in `agent.py` updated to extract all `RUNNER_UP:` lines using `re.findall`, returning them as a list of `{"name": ..., "reason": ...}` dicts.

## Section 3: Consolidated Summary in Orchestrator

`format_final_results` in `orchestrator.py` extended:

1. Collect all runner-ups from both agents (up to 10 total)
2. Deduplicate by name (case-insensitive), first occurrence wins
3. Drop any runner-up that matches the winning recommendation
4. Print up to 10 in a "Why not the others" section

Example output:
```
============================================================
FINAL RECOMMENDATIONS
============================================================

✅ CONSENSUS REACHED: Toyota RAV4 Hybrid 2023

Both agents agree: Best balance of resale value, space, and running costs within budget.

Why not the others:
  • Jaecoo J7 — Uncertain long-term resale value and limited service network
  • Skoda Kodiaq 2024 — Significantly over budget new; used options have high mileage
  • Kia Sorento — Higher insurance bracket in Israel
  ...
============================================================
```

## Files Changed

- `agent.py` — `build_system_prompt`, `parse_final_answer`
- `orchestrator.py` — `format_final_results`
- `tests/test_agent.py` — new tests for extended parser
- `tests/test_orchestrator.py` — updated summary formatter tests
