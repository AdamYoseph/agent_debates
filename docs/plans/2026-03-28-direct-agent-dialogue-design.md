# Direct Agent Dialogue — Design

**Date:** 2026-03-28

## Goal

Agents respond directly to each other's arguments and address each other by name, making the debate feel like a real back-and-forth exchange rather than two independent monologues.

## Approach

Context injection: the orchestrator finds the opponent's most recent message from history and adds a `RESPOND TO [name]'s latest argument:` section to each agent's context. The system prompt instructs agents to address opponents by name. No protocol changes required.

## Components

### `agent.py` — system prompt update

Add one sentence to `build_system_prompt(name)`:

> "When responding, address your opponent directly by their name. The context will indicate whose argument you should respond to."

### `debate.py` — `build_context` update

Add `opponent_name: str | None = None` parameter.

When `opponent_name` is provided:
- Scan `self.history` in reverse for the most recent entry from `opponent_name`
- If found, insert a `RESPOND TO [name]'s latest argument:` block containing their message, followed by `Address [name] directly by name in your response.`
- If not found (first turn, no history yet), skip the section silently

Section appears after `YOUR ROLE` and before `TOPIC`, so agents read the response directive first.

### `orchestrator.py` — pass opponent_name to build_context

In `debate_round` and `run_final_round`, for each `(name, conn)` pair, derive the opponent as the other connected agent:

```python
opponent_name = next(n for n, _ in connections if n != name)
context = state.build_context(agent_name=name, opponent_name=opponent_name)
```

No other changes needed.

## Data Flow

```
debate_round (per agent turn)
  └─ opponent_name = other agent's name
  └─ build_context(agent_name=name, opponent_name=opponent_name)
       ├─ YOUR ROLE: comfort focused
       ├─ RESPOND TO Beta's latest argument:   ← new
       │    [Beta's most recent message]
       │    Address Beta directly by name.
       ├─ TOPIC: ...
       ├─ RESEARCH BRIEF: ...
       ├─ DEBATE GUIDANCE: ...
       ├─ USER INFO: ...
       └─ DEBATE HISTORY: ...
```

## Testing

- `tests/test_debate.py` — add tests for:
  - `build_context` with `opponent_name` when opponent has history → "RESPOND TO" section present
  - `build_context` with `opponent_name` when no history yet → no "RESPOND TO" section
  - `build_context` with `opponent_name` picks the **most recent** opponent message, not the first
  - `build_context` without `opponent_name` → no "RESPOND TO" section (no regression)
