# agent.py
import os
import time
import socket
import argparse
import re
from google import genai
from google.genai import types
from config import Config
from protocol import Message, Signal
from socket_utils import send_message, recv_message
from search_tools import search_web, SEARCH_TOOL_DEFINITION
from logging_utils import setup_logging

MAX_TOOL_ITERATIONS = 5
RATE_LIMIT_WAIT = 65  # fallback wait for per-minute quota (seconds)
DAILY_QUOTA_WAIT = 300  # fallback wait for daily quota (seconds)
NETWORK_ERROR_WAIT = 30  # wait before retrying transient network errors (seconds)


def build_system_prompt(name: str) -> str:
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
directly by name and engage specifically with their argument before making your own points.

If there is NO "RESPOND TO" section, this is the opening round and your opponent has not \
spoken yet. Just make your own opening argument based on the TOPIC, RESEARCH BRIEF, and \
DEBATE GUIDANCE. Do not ask about your opponent — they will respond in their turn.

Use [NEED_INFO] ONLY when you are missing information about the USER's situation \
(e.g. budget, family size, lifestyle) that is not already provided in the context. \
Never use [NEED_INFO] to ask about the debate, the opponent, or their arguments.
[NEED_INFO]
1. What is your budget?
2. How many people are in your family?

When the orchestrator sends signal FINAL_ANSWER, respond ONLY in this exact format:
RECOMMENDATION: <Car make and model>
REASON: <2-3 sentences explaining why>
CONSENSUS: yes/no

Keep responses concise (3-5 sentences max) unless providing a FINAL_ANSWER."""


def _parse_retry_delay(err_str: str) -> int | None:
    """Extract the suggested retry delay (seconds) from a Gemini 429 error string."""
    match = re.search(r"retryDelay['\"]:\s*['\"](\d+)s", err_str)
    return int(match.group(1)) if match else None


def _gemini_call(fn, *args, logger=None):
    """Call a Gemini API function, retrying indefinitely on 429 quota errors.

    Uses the retryDelay from the API error when available; falls back to
    DAILY_QUOTA_WAIT for per-day limits and RATE_LIMIT_WAIT for per-minute limits.
    """
    attempt = 0
    while True:
        try:
            return fn(*args)
        except OSError as e:
            # Transient network error (DNS failure, connection reset, etc.)
            attempt += 1
            msg = f"Network error: {e}. Waiting {NETWORK_ERROR_WAIT}s before retry (attempt {attempt})..."
            print(msg)
            if logger:
                logger.warning(msg)
            time.sleep(NETWORK_ERROR_WAIT)
        except Exception as e:
            err_str = str(e)
            if "429" not in err_str:
                raise
            parsed = _parse_retry_delay(err_str)
            is_daily = "PerDay" in err_str
            if is_daily:
                wait = parsed if parsed else DAILY_QUOTA_WAIT
                kind = "Daily quota"
            else:
                wait = parsed if parsed else RATE_LIMIT_WAIT
                kind = "Rate limit"
            attempt += 1
            msg = f"{kind} hit. Waiting {wait}s before retry (attempt {attempt})..."
            print(msg)
            if logger:
                logger.warning(msg)
            time.sleep(wait)


def handle_tool_calls(response, chat, logger=None) -> str:
    """Execute any function calls in the response, feeding results back until plain text."""
    iteration = 0
    while response.function_calls and iteration < MAX_TOOL_ITERATIONS:
        tool_results = []
        for call in response.function_calls:
            if call.name == "search_web":
                query = call.args.get("query", "")
                max_results = call.args.get("max_results", 5)
                if logger:
                    logger.info(f"Tool call: search_web(query={query!r})")
                result = search_web(query, max_results=max_results)
                if logger:
                    logger.debug(f"search_web result: {result[:200]}")
            else:
                result = f"Unknown tool: {call.name}"
                if logger:
                    logger.warning(f"Unknown tool called: {call.name}")
            tool_results.append(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result},
                )
            )
        response = _gemini_call(chat.send_message, tool_results, logger=logger)
        iteration += 1
    if not response.text and logger:
        logger.warning("Gemini returned empty text after tool call loop")
    return response.text or ""


def parse_final_answer(response: str) -> dict:
    rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response)
    reason_match = re.search(r"REASON:\s*(.+)", response)
    consensus_match = re.search(r"CONSENSUS:\s*(yes|no)", response, re.IGNORECASE)

    return {
        "recommendation": rec_match.group(1).strip() if rec_match else "",
        "reason": reason_match.group(1).strip() if reason_match else "",
        "consensus": consensus_match.group(1).lower() == "yes"
        if consensus_match
        else False,
    }


def run_agent(name: str):
    logger = setup_logging(f"agent-{name}")
    logger.info(f"Agent {name} starting")

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
    logger.info("Connected to orchestrator")

    registration = Message(role="agent", name=name, content="ready", signal=None)
    send_message(sock, registration)

    while True:
        msg = recv_message(sock)

        if msg.signal == Signal.FINAL_ANSWER:
            print(f"\n[{name}] Generating final recommendation...")
            logger.info("Received FINAL_ANSWER signal")
            user_message = msg.content + "\n\nProvide your FINAL_ANSWER now."
        else:
            print(f"\n[{name}] Received: {msg.content[:80]}...")
            logger.info(f"Received message: {msg.content[:200]}")
            user_message = msg.content

        try:
            response = _gemini_call(chat.send_message, user_message, logger=logger)
            reply = handle_tool_calls(response, chat, logger=logger)
        except Exception as e:
            print(f"\n[{name}] ERROR calling Gemini API: {e}")
            logger.error(f"Gemini API error: {e}")
            sock.close()
            raise

        print(f"\n[{name}] My response:\n{reply}\n")
        logger.info(f"Response: {reply}")

        signal = None
        if reply.strip().startswith("[NEED_INFO]"):
            signal = Signal.NEED_INFO
            logger.info("Emitting NEED_INFO signal")

        out = Message(role="agent", name=name, content=reply, signal=signal)
        send_message(sock, out)

        if msg.signal == Signal.FINAL_ANSWER:
            break

    sock.close()
    logger.info("Debate complete. Disconnecting.")
    print(f"[{name}] Debate complete. Disconnecting.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Agent name (e.g. Alpha or Beta)")
    args = parser.parse_args()
    run_agent(args.name)
