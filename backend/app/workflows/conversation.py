"""Workflow 2 — conversational lead qualification, CRM capture & scheduling."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.agent.runner import FALLBACK_REPLY, AgentResult, run_agent
from app.notify import client_label, money, record

log = logging.getLogger(__name__)

MAIN_MENU = [
    [{"text": "🏠 Browse listings", "callback_data": "menu:browse"}],
    [
        {"text": "📅 Book a site visit", "callback_data": "menu:visit"},
        {"text": "📞 Request a call", "callback_data": "menu:call"},
    ],
]

MENU_PROMPTS = {
    "menu:browse": "Hi! Which properties do you currently have available?",
    "menu:visit": "I'd like to book an in-person site visit.",
    "menu:call": "I'd like to schedule a phone consultation with a sales agent.",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def converse(services: Any, client: dict, user_text: str, channel: str, display_text: str | None = None) -> AgentResult:
    """Run the agent for one user message and persist the exchange."""
    repo = services.repo
    try:
        result = run_agent(services, client, user_text, channel)
    except Exception:
        log.exception("agent failed for client %s", client["id"])
        result = AgentResult(reply=FALLBACK_REPLY, tool_calls=[])
        record(services, "error", f"Agent error while replying to {client_label(client)}", None, client["id"])

    repo.add_message(client["id"], "user", display_text or user_text, channel)
    for call in result.tool_calls:
        repo.add_message(
            client["id"], "tool", json.dumps({"tool": call["name"], "args": call["args"], "result": call["result"]}, default=str), channel
        )
    repo.add_message(client["id"], "assistant", result.reply, channel)
    client.update(repo.update_client(client["id"], {"last_contact_at": _now_iso()}))
    record(
        services,
        "conversation",
        f"{client_label(client)} ({channel}): “{(display_text or user_text)[:80]}”",
        {"user": display_text or user_text, "reply": result.reply, "tools": [c["name"] for c in result.tool_calls]},
        client["id"],
    )
    return result


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def get_or_create_telegram_client(services: Any, user: dict, chat_id: int) -> dict:
    repo = services.repo
    client = repo.get_client_by_telegram(chat_id)
    username = user.get("username")
    if client:
        if username and client.get("telegram_username") != username:
            client = repo.update_client(client["id"], {"telegram_username": username})
        return client
    display_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    client = repo.create_client(
        {
            "telegram_chat_id": chat_id,
            "telegram_username": username,
            "status": "LEAD",
            "notes": f"Telegram display name: {display_name}" if display_name else None,
        }
    )
    record(services, "new_lead", f"New Telegram lead: {display_name or '@' + str(username)}", None, client["id"])
    return client


def _send_property_deep_link(
    services: Any, client: dict, chat_id: int, prop: dict, kind: str, user_from: dict | None = None
) -> None:
    tg = services.telegram
    settings = services.settings
    currency = settings.currency

    first_name = (
        client.get("full_name")
        or (user_from or {}).get("first_name")
        or client.get("telegram_username")
        or ""
    ).strip()
    greeting = f"Hi {first_name}! 👋" if first_name else "Hello! 👋"

    price_str = money(prop.get("price"), currency)
    per_sqm = f" ({money(prop.get('price_per_sqm'), currency)}/m²)" if prop.get("price_per_sqm") else ""

    if kind == "plan":
        lines = [
            f"{greeting} Here are the financing & payment plan details for {prop['name']}:",
            "",
            f"🏡 Property: {prop['name']}",
        ]
        if prop.get("location"):
            lines.append(f"📍 Location: {prop['location']}")
        if prop.get("price"):
            lines.append(f"💰 Total Price: {price_str}{per_sqm}")
        if prop.get("down_payment"):
            lines.append(f"💵 Down Payment: {prop['down_payment']}")
        if prop.get("payment_plan"):
            lines.append(f"💳 Payment Schedule: {prop['payment_plan']}")
        if prop.get("construction_status"):
            lines.append(f"🏗 Construction: {prop['construction_status']}")
        lines += [
            "",
            f"I'm {settings.agent_name}, your dedicated sales executive. Would you like to book a site visit to view the units, or schedule a phone consultation to discuss tailored financing options?",
        ]
    else:
        specs = []
        if prop.get("bedrooms"):
            specs.append(f"{prop['bedrooms']} bedrooms")
        if prop.get("area_sqm"):
            specs.append(f"{prop['area_sqm']} m²")
        specs_str = " · ".join(specs)

        lines = [
            f"{greeting} Welcome to {settings.company_name}! Here is the overview for {prop['name']}:",
            "",
            f"🏡 Property: {prop['name']}",
        ]
        if prop.get("location"):
            lines.append(f"📍 Location: {prop['location']}")
        if prop.get("price"):
            lines.append(f"💰 Price: {price_str}{per_sqm}")
        if specs_str:
            lines.append(f"🛏 Specifications: {specs_str}")
        if prop.get("payment_plan"):
            lines.append(f"💳 Payment Plan: {prop['payment_plan']}")
        if prop.get("construction_status"):
            lines.append(f"🏗 Status: {prop['construction_status']}")
        if prop.get("description"):
            lines.append(f"\n{prop['description']}")
        lines += [
            "",
            f"I'm {settings.agent_name}, your dedicated sales executive. Would you like to book an in-person site visit or schedule a phone consultation?",
        ]

    buttons = [
        [
            {"text": "📅 Book Site Visit", "callback_data": f"visit:{prop['id']}"},
            {"text": "📞 Schedule Telegram Call", "callback_data": f"call:{prop['id']}"},
        ]
    ]

    text = "\n".join(lines)
    sent = False
    if prop.get("image_url"):
        try:
            tg.send_photo(chat_id, prop["image_url"], text[:1024], buttons)
            sent = True
        except Exception as exc:
            log.warning("send_photo failed (%s), sending text", exc)
    if not sent:
        tg.send_message(chat_id, text, buttons)

    services.repo.add_message(client["id"], "user", f"/start {kind}_{prop['id']}", "telegram")
    services.repo.add_message(client["id"], "assistant", text, "telegram")
    record(
        services,
        "conversation",
        f"{client_label(client)} (telegram): “/start {kind}_{prop['id']}”",
        {"property_id": prop["id"], "kind": kind},
        client["id"],
    )


def _start_payload_text(services: Any, client: dict, payload: str) -> str | None:
    """Translate an ad deep-link (/start prop_<id>, plan_<id>, or visit_<id>) into a natural opening message."""
    kind, _, property_id = payload.partition("_")
    if kind not in ("prop", "plan", "visit", "call") or not property_id:
        return None
    prop = services.repo.get_property(property_id)
    if not prop:
        return None
    client.update(services.repo.update_client(client["id"], {"interested_property_id": prop["id"]}))
    if kind == "visit":
        return f"Hi! I saw your ad for {prop['name']} and I'd like to book a site visit."
    if kind == "plan":
        return f"Hi! I saw your ad for {prop['name']} and I'd like details on the financing and payment plan."
    if kind == "call":
        return f"Hi! I'd like to schedule a phone consultation to discuss {prop['name']}."
    return f"Hi! I saw your ad for {prop['name']} and I'd like to know more about it."


def handle_telegram_update(services: Any, update: dict) -> None:
    tg = services.telegram

    if callback := update.get("callback_query"):
        tg.answer_callback(callback["id"])
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") != "private":
            return
        data = callback.get("data", "")
        client = get_or_create_telegram_client(services, callback["from"], chat["id"])
        if data.startswith(("visit:", "prop:", "plan:", "call:")):
            kind, _, prop_id = data.partition(":")
            prop = services.repo.get_property(prop_id) if prop_id else None
            prop_name = prop["name"] if prop else "this property"
            if prop:
                client.update(services.repo.update_client(client["id"], {"interested_property_id": prop["id"]}))
            if kind == "visit":
                text = f"I would like to book an in-person site visit for {prop_name}."
            elif kind == "call":
                text = f"I would like to schedule a phone consultation to discuss {prop_name}."
            elif kind == "plan":
                text = f"Can you tell me more about the payment plan for {prop_name}?"
            else:
                text = f"Can you tell me more about {prop_name}?"
            _reply(services, client, chat["id"], text, display_text=f"Selected: {text}")
            return
        else:
            text = MENU_PROMPTS.get(data)
        if text:
            _reply(services, client, chat["id"], text)
        return

    message = update.get("message")
    if not message or (message.get("chat") or {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    client = get_or_create_telegram_client(services, message.get("from") or {}, chat_id)

    if contact := message.get("contact"):
        services.repo.update_client(client["id"], {"phone": contact.get("phone_number")})
        client["phone"] = contact.get("phone_number")
        _reply(services, client, chat_id, f"Here is my phone number: {contact.get('phone_number')}")
        return

    text = (message.get("text") or "").strip()
    if not text:
        tg.send_message(chat_id, "I can only read text messages for now — please type your question 🙂")
        return

    if text.startswith("/start"):
        payload = text.removeprefix("/start").strip()
        kind, _, property_id = payload.partition("_")
        if kind in ("prop", "plan") and property_id:
            prop = services.repo.get_property(property_id)
            if prop:
                client.update(services.repo.update_client(client["id"], {"interested_property_id": prop["id"]}))
                _send_property_deep_link(services, client, chat_id, prop, kind, message.get("from"))
                return

        opening = _start_payload_text(services, client, payload) if payload else None
        if opening:
            _reply(services, client, chat_id, opening, display_text=f"/start {payload}")
            return
        settings = services.settings
        welcome = (
            f"👋 Welcome to {settings.company_name}! I'm {settings.agent_name}, your property assistant.\n\n"
            "I can show you available homes, answer questions about prices and payment plans, "
            "and book a call or site visit for you. How can I help?"
        )
        services.repo.add_message(client["id"], "user", "/start", "telegram")
        services.repo.add_message(client["id"], "assistant", welcome, "telegram")
        tg.send_message(chat_id, welcome, MAIN_MENU)
        return

    _reply(services, client, chat_id, text)


def _reply(services: Any, client: dict, chat_id: int, text: str, display_text: str | None = None) -> None:
    services.telegram.send_typing(chat_id)
    result = converse(services, client, text, "telegram", display_text)
    services.telegram.send_message(chat_id, result.reply)


# ---------------------------------------------------------------------------
# Web dashboard chat (evaluator test path)
# ---------------------------------------------------------------------------
def handle_web_message(services: Any, session_id: str, text: str) -> dict:
    repo = services.repo
    client = repo.get_client_by_web_session(session_id)
    if not client:
        client = repo.create_client({"web_session_id": session_id, "status": "LEAD", "notes": "Web chat lead"})
        record(services, "new_lead", "New web-chat lead", None, client["id"])
    result = converse(services, client, text, "web")
    return {"reply": result.reply, "tool_calls": result.tool_calls, "client": client}
