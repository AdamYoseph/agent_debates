# Web Search Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give debate agents real-time web search via DuckDuckGo — both a pre-loaded research brief at startup and dynamic mid-debate lookups via Gemini native function calling.

**Architecture:** A new `search_tools.py` provides `search_web()` and `pre_search()`. The orchestrator runs `pre_search()` before the debate and stores the brief in `DebateState`. Each agent registers `search_web` as a Gemini tool and handles function-call responses in a loop before replying.

**Tech Stack:** `duckduckgo-search>=6.0.0`, `google-genai`, Gemini function calling API, pytest

---

### Task 1: Add duckduckgo-search dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add the package**

Edit `requirements.txt` to:
```
google-genai>=1.0.0
pytest>=7.0.0
duckduckgo-search>=6.0.0
```

**Step 2: Install it**

Run: `pip install duckduckgo-search`
Expected: Successfully installed duckduckgo-search

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add duckduckgo-search dependency"
```

---

### Task 2: Create `search_tools.py` with `search_web`

**Files:**
- Create: `search_tools.py`
- Create: `tests/test_search_tools.py`

**Step 1: Write the failing test**

Create `tests/test_search_tools.py`:
```python
# tests/test_search_tools.py
from unittest.mock import patch, MagicMock
from search_tools import search_web, SEARCH_TOOL_DEFINITION


def test_search_web_returns_string():
    mock_results = [
        {"title": "Toyota RAV4 Price", "body": "Costs $30,000 in Israel", "href": "https://example.com"},
        {"title": "Honda CR-V Review", "body": "Great family car", "href": "https://example2.com"},
    ]
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.return_value = mock_results
        result = search_web("best family car Israel")

    assert "Toyota RAV4 Price" in result
    assert "Costs $30,000 in Israel" in result
    assert "https://example.com" in result


def test_search_web_empty_results():
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.return_value = []
        result = search_web("something obscure")

    assert result == "No results found."


def test_search_web_handles_exception():
    with patch("search_tools.DDGS") as MockDDGS:
        instance = MockDDGS.return_value.__enter__.return_value
        instance.text.side_effect = Exception("network error")
        result = search_web("test query")

    assert result == "Search failed."


def test_search_tool_definition_structure():
    assert SEARCH_TOOL_DEFINITION["name"] == "search_web"
    assert "query" in SEARCH_TOOL_DEFINITION["parameters"]["properties"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_search_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'search_tools'`

**Step 3: Implement `search_tools.py`**

Create `search_tools.py`:
```python
# search_tools.py
from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search and return formatted results."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"{r['title']} | {r['body']} | {r['href']}")
        return "\n".join(lines)
    except Exception:
        return "Search failed."


SEARCH_TOOL_DEFINITION = {
    "name": "search_web",
    "description": (
        "Search the web for current information about car prices, insurance rates, "
        "reliability ratings, and other relevant data. Use this when you need specific "
        "facts or figures to support your argument."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query, e.g. 'Toyota RAV4 price Israel 2025'",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    },
}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search_tools.py -v`
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add search_tools.py tests/test_search_tools.py
git commit -m "feat: add search_web and SEARCH_TOOL_DEFINITION"
```

---

### Task 3: Add `pre_search` to `search_tools.py`

**Files:**
- Modify: `search_tools.py`
- Modify: `tests/test_search_tools.py`

**Step 1: Write the failing test**

Append to `tests/test_search_tools.py`:
```python
def test_pre_search_returns_non_empty_string():
    with patch("search_tools.search_web", return_value="some car data"):
        from search_tools import pre_search
        result = pre_search("best family SUV")

    assert len(result) > 0
    assert "RESEARCH BRIEF" in result


def test_pre_search_includes_multiple_queries():
    call_log = []

    def fake_search(query, **kwargs):
        call_log.append(query)
        return "data"

    with patch("search_tools.search_web", side_effect=fake_search):
        from search_tools import pre_search
        pre_search("Toyota RAV4")

    assert len(call_log) >= 4
    assert any("Israel" in q for q in call_log)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search_tools.py::test_pre_search_returns_non_empty_string -v`
Expected: FAIL with `ImportError: cannot import name 'pre_search'`

**Step 3: Implement `pre_search`**

Add to `search_tools.py` (after `search_web`):
```python
def pre_search(topic: str) -> str:
    """Run targeted searches before the debate starts. Returns a research brief."""
    queries = [
        f"{topic} price Israel 2025",
        f"{topic} insurance cost Israel",
        f"{topic} reliability rating",
        f"best family car Israel 2025 recommendations",
        f"{topic} fuel economy",
        f"{topic} maintenance cost",
    ]
    sections = ["## RESEARCH BRIEF\n"]
    for query in queries:
        result = search_web(query, max_results=3)
        sections.append(f"### {query}\n{result}\n")
    return "\n".join(sections)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search_tools.py -v`
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add search_tools.py tests/test_search_tools.py
git commit -m "feat: add pre_search for debate warmup research"
```

---

### Task 4: Add `research_brief` to `DebateState`

**Files:**
- Modify: `debate.py`
- Modify: `tests/test_debate.py`

**Step 1: Write the failing tests**

Append to `tests/test_debate.py`:
```python
def test_research_brief_default_empty():
    state = DebateState(topic="Best family SUV")
    assert state.research_brief == ""


def test_build_context_includes_research_brief():
    state = DebateState(topic="Best family SUV", research_brief="Toyota costs $30k")
    context = state.build_context()
    assert "Toyota costs $30k" in context
    assert "RESEARCH BRIEF" in context


def test_build_context_omits_brief_when_empty():
    state = DebateState(topic="Best family SUV")
    context = state.build_context()
    assert "RESEARCH BRIEF" not in context
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_debate.py::test_research_brief_default_empty -v`
Expected: FAIL with `TypeError: unexpected keyword argument 'research_brief'`

**Step 3: Update `DebateState`**

In `debate.py`, add the field and update `build_context`:

```python
@dataclass
class DebateState:
    topic: str
    rounds_per_segment: int = Config.ROUNDS_PER_SEGMENT
    phase: DebatePhase = DebatePhase.DEBATING
    round: int = 0
    history: List[dict] = field(default_factory=list)
    user_info: List[str] = field(default_factory=list)
    research_brief: str = ""

    # ... existing methods unchanged ...

    def build_context(self) -> str:
        """Build a conversation context string for agents."""
        lines = [f"TOPIC: {self.topic}"]
        if self.research_brief:
            lines.append(f"\n{self.research_brief}")
        if self.user_info:
            lines.append("\nUSER INFO PROVIDED:")
            for info in self.user_info:
                lines.append(f"  - {info}")
        lines.append("\nDEBATE HISTORY:")
        for entry in self.history:
            lines.append(f"  {entry['name']}: {entry['content']}")
        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_debate.py -v`
Expected: all 10 tests PASS

**Step 5: Commit**

```bash
git add debate.py tests/test_debate.py
git commit -m "feat: add research_brief field to DebateState"
```

---

### Task 5: Wire pre_search into orchestrator

**Files:**
- Modify: `orchestrator.py`

**Step 1: Add import and pre_search call**

In `orchestrator.py`:

1. Add import at the top:
```python
from search_tools import pre_search
```

2. Update `run_debate` — add pre_search call right after topic is known, before collecting agents:
```python
def run_debate(topic: str) -> None:
    print(f"\nResearching '{topic}'...")
    brief = pre_search(topic)
    state = DebateState(topic=topic, research_brief=brief)
    # rest unchanged
```

**Step 2: Run existing orchestrator tests**

Run: `pytest tests/test_orchestrator.py -v`
Expected: all tests PASS (no changes to tested functions)

**Step 3: Commit**

```bash
git add orchestrator.py
git commit -m "feat: run pre_search before debate starts"
```

---

### Task 6: Add Gemini function calling to agent

**Files:**
- Modify: `agent.py`
- Modify: `tests/test_agent.py`

**Step 1: Write the failing test**

The tool-call loop is the key logic to test. Append to `tests/test_agent.py`:
```python
from unittest.mock import MagicMock, patch
from agent import handle_tool_calls


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent.py::test_handle_tool_calls_no_function_calls -v`
Expected: FAIL with `ImportError: cannot import name 'handle_tool_calls'`

**Step 3: Implement `handle_tool_calls` and update `run_agent`**

Update `agent.py`:

```python
# agent.py
import os
import socket
import argparse
import re
from google import genai
from google.genai import types
from config import Config
from protocol import Message, Signal
from socket_utils import send_message, recv_message
from search_tools import search_web, SEARCH_TOOL_DEFINITION

MAX_TOOL_ITERATIONS = 5


def build_system_prompt(name: str) -> str:
    return f"""You are a car-buying advisor named {name}. You are debating another advisor \
about the best car for the user's family. Take a dynamic position based on the conversation \
— let the arguments and evidence guide you, don't be assigned a fixed side.

You have access to a search_web tool. Use it to look up current car prices, insurance rates, \
reliability data, or any specific facts that would strengthen your argument.

When you need information from the user to make a better recommendation, start your response \
with [NEED_INFO] followed by a numbered list of what you need. Example:
[NEED_INFO]
1. What is your budget?
2. How many people are in your family?

When the orchestrator sends signal FINAL_ANSWER, respond ONLY in this exact format:
RECOMMENDATION: <Car make and model>
REASON: <2-3 sentences explaining why>
CONSENSUS: yes/no

Keep responses concise (3-5 sentences max) unless providing a FINAL_ANSWER."""


def handle_tool_calls(response, chat) -> str:
    """Execute any function calls in the response, feeding results back until plain text."""
    iteration = 0
    while response.function_calls and iteration < MAX_TOOL_ITERATIONS:
        tool_results = []
        for call in response.function_calls:
            if call.name == "search_web":
                query = call.args.get("query", "")
                max_results = call.args.get("max_results", 5)
                result = search_web(query, max_results=max_results)
            else:
                result = f"Unknown tool: {call.name}"
            tool_results.append(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result},
                )
            )
        response = chat.send_message(tool_results)
        iteration += 1
    return response.text or ""


def parse_final_answer(response: str) -> dict:
    rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response)
    reason_match = re.search(r"REASON:\s*(.+)", response)
    consensus_match = re.search(r"CONSENSUS:\s*(yes|no)", response, re.IGNORECASE)

    return {
        "recommendation": rec_match.group(1).strip() if rec_match else "",
        "reason": reason_match.group(1).strip() if reason_match else "",
        "consensus": consensus_match.group(1).lower() == "yes" if consensus_match else False,
    }


def run_agent(name: str):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    tool = types.Tool(function_declarations=[SEARCH_TOOL_DEFINITION])

    chat = client.chats.create(
        model=Config.MODEL,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(name),
            max_output_tokens=Config.MAX_TOKENS,
            tools=[tool],
        ),
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((Config.HOST, Config.PORT))
    print(f"[{name}] Connected to orchestrator.")

    registration = Message(role="agent", name=name, content="ready", signal=None)
    send_message(sock, registration)

    while True:
        msg = recv_message(sock)

        if msg.signal == Signal.FINAL_ANSWER:
            print(f"\n[{name}] Generating final recommendation...")
            user_message = msg.content + "\n\nProvide your FINAL_ANSWER now."
        else:
            print(f"\n[{name}] Received: {msg.content[:80]}...")
            user_message = msg.content

        try:
            response = chat.send_message(user_message)
            reply = handle_tool_calls(response, chat)
        except Exception as e:
            print(f"\n[{name}] ERROR calling Gemini API: {e}")
            sock.close()
            raise

        print(f"\n[{name}] My response:\n{reply}\n")

        signal = None
        if reply.strip().startswith("[NEED_INFO]"):
            signal = Signal.NEED_INFO

        out = Message(role="agent", name=name, content=reply, signal=signal)
        send_message(sock, out)

        if msg.signal == Signal.FINAL_ANSWER:
            break

    sock.close()
    print(f"[{name}] Debate complete. Disconnecting.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Agent name (e.g. Alpha or Beta)")
    args = parser.parse_args()
    run_agent(args.name)
```

**Step 4: Run all agent tests**

Run: `pytest tests/test_agent.py -v`
Expected: all 8 tests PASS

**Step 5: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: add Gemini function calling with search_web tool"
```

---

### Task 7: Run full test suite

**Step 1: Run all tests**

Run: `pytest -v`
Expected: all tests PASS

**Step 2: Fix any failures before proceeding**

If any test fails, fix the root cause — do not skip or comment out tests.

**Step 3: Commit if any fixes were needed**

```bash
git add -p
git commit -m "fix: address test failures after web search integration"
```
