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
