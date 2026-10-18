"""Manual Gemini function-calling loop for the sales agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from google.genai import types

from app.agent.prompts import build_system_prompt
from app.agent.tools import TOOL, AgentContext, execute_tool
from app.notify import record

log = logging.getLogger(__name__)

MAX_STEPS = 6
HISTORY_LIMIT = 20
FALLBACK_REPLY = "Sorry, I'm having a little trouble right now. A member of our sales team will get back to you shortly 🙏"


@dataclass
class AgentResult:
    reply: str
    tool_calls: list[dict]


def history_to_contents(messages: list[dict]) -> list[types.Content]:
    """Convert stored user/assistant messages into Gemini contents (starting with a user turn, roles merged)."""
    contents: list[types.Content] = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        if not contents and role == "model":
            continue
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part.from_text(text=msg["content"]))
        else:
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    return contents


def _agent_context_extras(services: Any, client: dict, now: datetime) -> dict:
    repo = services.repo
    extras: dict[str, Any] = {}
    if client.get("interested_property_id"):
        extras["interested_property"] = repo.get_property(client["interested_property_id"])
    extras["upcoming_appointments"] = [
        a
        for a in repo.list_appointments(start_from=now, start_to=now + timedelta(days=30), client_id=client["id"])
        if a.get("status") == "SCHEDULED"
    ]
    if client.get("status") == "CLOSED_BUYER":
        extras["contracts"] = repo.list_contracts(client_id=client["id"])
    return extras


def run_agent(services: Any, client: dict, user_text: str, channel: str, now: datetime | None = None) -> AgentResult:
    """Run one conversational turn. `client` is mutated in place if the profile changes."""
    settings = services.settings
    now = now or datetime.now(settings.tz)
    ctx = AgentContext(services=services, client=client, channel=channel, now=now)

    history = services.repo.recent_messages(client["id"], HISTORY_LIMIT, roles=("user", "assistant"))
    contents = history_to_contents(history)
    user_part = types.Part.from_text(text=user_text)
    if contents and contents[-1].role == "user":
        contents[-1].parts.append(user_part)
    else:
        contents.append(types.Content(role="user", parts=[user_part]))

    system = build_system_prompt(settings, client, channel, now, **_agent_context_extras(services, client, now))
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[TOOL],
        temperature=0.4,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    reply = ""
    for step in range(MAX_STEPS):
        response = services.gemini.generate(contents, config)
        calls = response.function_calls or []
        if not calls:
            reply = (response.text or "").strip()
            break
        contents.append(response.candidates[0].content)
        parts = []
        for call in calls:
            args = dict(call.args or {})
            result = execute_tool(ctx, call.name, args)
            record(
                services,
                "tool_call",
                f"{call.name}({', '.join(f'{k}={v}' for k, v in args.items())})",
                {"tool": call.name, "args": args, "result": result},
                client["id"],
            )
            parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=parts))
    else:
        log.warning("agent hit MAX_STEPS for client %s", client["id"])

    return AgentResult(reply=reply or FALLBACK_REPLY, tool_calls=ctx.tool_log)


def summarize_tool_calls(tool_calls: list[dict]) -> str:
    return json.dumps([{"tool": t["name"], "args": t["args"]} for t in tool_calls], default=str)
