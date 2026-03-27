# Web Search Tools for Debate Agents — Design

**Date:** 2026-03-28

## Goal

Give agents access to real-world data (car prices, insurance rates, reliability) so debates are grounded in current facts rather than training-data estimates.

## Approach

Two-layer search strategy:

1. **Pre-load** — orchestrator runs targeted DuckDuckGo searches before the debate starts and injects a research brief into every agent's context.
2. **Dynamic** — agents call `search_web` mid-debate via Gemini native function calling whenever they need specific data points.

Search provider: DuckDuckGo via `duckduckgo-search` Python package (free, no API key).

## Components

### `search_tools.py` (new)

- `search_web(query: str, max_results: int = 5) -> str` — executes a DuckDuckGo text search and returns a formatted string of `title | snippet | url` lines. Used both as a callable for the pre-load and as the handler for Gemini function calls.
- `pre_search(topic: str) -> str` — runs 5–6 targeted queries (e.g. `"{topic} price Israel 2025"`, `"car insurance Israel 2025"`, `"{topic} reliability"`) and compiles results into a single research brief string.
- `SEARCH_TOOL_DEFINITION` — Gemini function declaration dict for `search_web`, consumed by `agent.py` when creating the chat session.

### `orchestrator.py` changes

- Call `pre_search(topic)` before entering the debate loop.
- Store the brief in a new `research_brief: str` field on `DebateState` (default `""`).
- `DebateState.build_context()` prepends the brief under a `## Research Brief` heading so every agent message includes it.

### `agent.py` changes

- Pass `SEARCH_TOOL_DEFINITION` in the `tools` config when creating the Gemini chat session.
- After `chat.send_message(...)`, enter a tool-call loop:
  - While the response contains function calls, execute each `search_web` call and send results back via `chat.send_message` with tool-result parts.
  - Exit loop when the response is plain text.
- Update system prompt to mention agents can call the search tool for current prices and data.

### `debate.py` changes

- Add `research_brief: str = ""` field to `DebateState`.
- Update `build_context()` to include the brief if non-empty.

### `requirements.txt`

- Add `duckduckgo-search>=6.0.0`

## Data Flow

```
orchestrator startup
  └─ pre_search(topic) → research_brief
  └─ DebateState(research_brief=...)

debate_round
  └─ build_context() includes brief
  └─ send context to agents

agent (per message)
  └─ chat.send_message(context)
  └─ if function_calls → search_web() → feed results → repeat
  └─ return final text → send back to orchestrator
```

## Error Handling

- DuckDuckGo search failures are caught and return an empty string (debate continues without that data point).
- Function call loop capped at 5 iterations to prevent infinite loops.

## Testing

- `tests/test_search_tools.py` — unit tests for `search_web` and `pre_search` using mocked DuckDuckGo responses.
- `tests/test_debate.py` — add test for `build_context` with `research_brief` populated.
- `tests/test_agent.py` — add test for tool-call loop helper (pure function, no API calls).
