# Agent Motivations & Debate Guidance — Design

**Date:** 2026-03-28

## Goal

Let users shape the debate by giving each agent a distinct motivation (e.g. "comfort focused", "cost focused") and an optional guidance block (e.g. "budget 150–250k ILS") — all set interactively at startup via the orchestrator.

## Approach

Context injection: motivations and guidance are stored on `DebateState` and injected into every context message the orchestrator sends to agents. No protocol changes, no agent changes.

## Startup Flow

After collecting the topic, the orchestrator asks interactively (in `collect_debate_setup`):

1. For each agent name (in connection order): `Alpha's motivation? (leave blank to skip)`
2. `Debate guidance/constraints? (leave blank to skip)`

These are optional — blank input means no motivation / no guidance.

## Components

### `DebateState` changes (`debate.py`)

Two new optional fields:
- `agent_motivations: dict` — `{"Alpha": "comfort focused", "Beta": "cost focused"}`, default `{}`
- `guidance: str` — free-text constraints, default `""`

`build_context(agent_name=None)` updated:
- If `agent_name` is in `agent_motivations`, prepend `YOUR ROLE: <motivation>` at the top
- If `guidance` is non-empty, append a `DEBATE GUIDANCE:` block before the history

### `orchestrator.py` changes

New function `collect_debate_setup(connections) -> tuple[dict, str]`:
- Loops over connected agents and prompts for each motivation
- Prompts for guidance
- Returns `(agent_motivations, guidance)`

`run_debate` updated:
- Calls `collect_debate_setup(connections)` after agents connect
- Passes `agent_motivations` and `guidance` into `DebateState`

`debate_round` updated:
- Passes `agent_name=name` to `build_context()` so each agent gets a personalized context

## Data Flow

```
orchestrator startup
  └─ get_topic() → topic
  └─ pre_search(topic) → brief
  └─ collect_agents() → connections
  └─ collect_debate_setup(connections) → agent_motivations, guidance
  └─ DebateState(topic, research_brief, agent_motivations, guidance)

debate_round (per agent)
  └─ build_context(agent_name=name)
       ├─ YOUR ROLE: comfort focused   ← per-agent motivation
       ├─ TOPIC: ...
       ├─ RESEARCH BRIEF: ...
       ├─ DEBATE GUIDANCE: ...         ← shared guidance
       ├─ USER INFO: ...
       └─ DEBATE HISTORY: ...
```

## Testing

- `tests/test_debate.py` — add tests for `agent_motivations` default, `build_context` with motivation, `build_context` with guidance, both together, neither
- `tests/test_orchestrator.py` — no new tests needed (setup is interactive I/O, not unit-testable without mocking)
