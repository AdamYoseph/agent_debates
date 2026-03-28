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
RATE_LIMIT_WAIT = 65  # seconds to wait on 429 (free tier is 5 req/min)
MAX_RETRIES = 3


def build_system_prompt(name: str) -> str:
    return f"""You are a car-buying advisor named {name}. You are debating another advisor \
about the best car for the user's family. Take a dynamic position based on the conversation \
— let the arguments and evidence guide you, don't be assigned a fixed side.

You have access to a search_web tool. Use it to look up current car prices, insurance rates, \
reliability data, or any specific facts that would strengthen your argument.

When the context shows a "RESPOND TO [name]'s latest argument" section, address that person \
directly by name and engage specifically with their argument before making your own points.

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


class DailyQuotaExceededError(Exception):
    """Raised when the Gemini daily request quota is exhausted."""


def _is_daily_quota_error(e: Exception) -> bool:
    err_str = str(e)
    return "429" in err_str and "PerDay" in err_str


def _gemini_call(fn, *args, logger=None):
    """Call a Gemini API function, retrying up to MAX_RETRIES times on per-minute 429 errors.

    Raises DailyQuotaExceededError immediately (no retry) when the daily quota is hit.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args)
        except Exception as e:
            if "429" in str(e):
                if _is_daily_quota_error(e):
                    msg = "Daily API quota exhausted. Cannot retry until tomorrow or billing is upgraded."
                    if logger:
                        logger.error(msg)
                    raise DailyQuotaExceededError(msg) from e
                if attempt < MAX_RETRIES - 1:
                    msg = f"Rate limit hit. Waiting {RATE_LIMIT_WAIT}s before retry ({attempt + 1}/{MAX_RETRIES - 1})..."
                    print(msg)
                    if logger:
                        logger.warning(msg)
                    time.sleep(RATE_LIMIT_WAIT)
                else:
                    raise
            else:
                raise


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
        except DailyQuotaExceededError as e:
            logger.error(f"Gemini API error: {e}")
            if msg.signal == Signal.FINAL_ANSWER:
                # Send a graceful fallback so the orchestrator can still display results
                fallback = (
                    "RECOMMENDATION: Unable to generate — daily API quota exhausted\n"
                    "REASON: The free-tier Gemini API limit (20 requests/day) was reached before "
                    "the final answer could be generated. Upgrade billing or retry tomorrow.\n"
                    "CONSENSUS: no"
                )
                print(f"\n[{name}] Daily quota hit. Sending fallback final answer.")
                out = Message(role="agent", name=name, content=fallback, signal=None)
                send_message(sock, out)
                sock.close()
                return
            print(f"\n[{name}] Daily quota exhausted: {e}")
            sock.close()
            raise
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
