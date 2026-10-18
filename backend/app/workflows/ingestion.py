"""Workflow 1 — company update ingestion, ad publishing & targeted lead broadcasts."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.notify import money, notify_client, record
from app.services.email import details_table, paragraphs

log = logging.getLogger(__name__)

BUDGET_TOLERANCE = 1.10  # a listing up to 10% above a lead's max budget is still worth sharing


class AnnouncementExtraction(BaseModel):
    announcement_type: Literal["NEW_LISTING", "PRICE_UPDATE", "PROMOTION", "STATUS_UPDATE", "OTHER"]
    property_name: str = Field(description="Exact existing property name if it refers to one, else the new name")
    location: str | None = None
    price: float | None = Field(None, description="Total unit price (numbers only)")
    price_per_sqm: float | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    down_payment: str | None = Field(None, description="e.g. '30%'")
    payment_plan: str | None = None
    construction_status: str | None = None
    description: str | None = Field(None, description="1-2 sentence description of the property")
    discount_percent: float | None = None
    key_change: str = Field(description="One sentence summarising what is new in this announcement")


PROPERTY_FIELDS = (
    "location",
    "price",
    "price_per_sqm",
    "bedrooms",
    "area_sqm",
    "down_payment",
    "payment_plan",
    "construction_status",
    "description",
)

PARSE_SYSTEM = (
    "You extract structured real-estate data from company announcements (emails, memos, chat posts). "
    "Only use facts present in the text; leave unknown fields null. Prices are plain numbers in {currency}. "
    "If the announcement refers to one of the existing properties, set property_name to its exact existing name.\n"
    "Existing properties: {existing}"
)

AD_SYSTEM = (
    "You are a top real-estate copywriter for {company}. Write a persuasive Telegram channel post "
    "(plain text, no Markdown, max 900 characters) with a catchy first line, 4-6 emoji bullet points "
    "with the key facts (location, price, bedrooms/size, payment plan, construction status, any discount), "
    "and a short call to action telling readers to tap the buttons below to ask questions or book a site visit. "
    "Never invent facts. Prices in {currency}."
)


# ---------------------------------------------------------------------------
# Parsing & copywriting
# ---------------------------------------------------------------------------
def parse_announcement(services: Any, raw_text: str) -> AnnouncementExtraction:
    settings = services.settings
    existing = ", ".join(p["name"] for p in services.repo.list_properties()) or "none"
    return services.gemini.structured(
        f"Announcement:\n\"\"\"\n{raw_text}\n\"\"\"",
        AnnouncementExtraction,
        system=PARSE_SYSTEM.format(currency=settings.currency, existing=existing),
    )


def generate_ad_copy(services: Any, extraction: AnnouncementExtraction, prop: dict) -> str:
    settings = services.settings
    facts = {k: prop.get(k) for k in ("name", *PROPERTY_FIELDS) if prop.get(k) not in (None, "")}
    if extraction.discount_percent:
        facts["discount_percent"] = extraction.discount_percent
    prompt = (
        f"Announcement type: {extraction.announcement_type}\nWhat's new: {extraction.key_change}\n"
        f"Property facts: {facts}\nFormatted price: {money(prop.get('price'), settings.currency)}"
    )
    try:
        copy = services.gemini.text(prompt, system=AD_SYSTEM.format(company=settings.company_name, currency=settings.currency))
        return copy.replace("**", "").strip()
    except Exception:
        log.exception("ad copy generation failed — using template")
        return fallback_ad_copy(extraction, prop, settings.currency)


def fallback_ad_copy(extraction: AnnouncementExtraction, prop: dict, currency: str) -> str:
    lines = [f"🏡 {prop['name']} — {extraction.key_change}", ""]
    if prop.get("location"):
        lines.append(f"📍 {prop['location']}")
    if prop.get("price"):
        lines.append(f"💰 {money(prop['price'], currency)}")
    if prop.get("bedrooms"):
        lines.append(f"🛏 {prop['bedrooms']} bedrooms" + (f" · {prop['area_sqm']} m²" if prop.get("area_sqm") else ""))
    if prop.get("payment_plan"):
        lines.append(f"💳 {prop['payment_plan']}")
    if prop.get("construction_status"):
        lines.append(f"🏗 {prop['construction_status']}")
    lines += ["", "👇 Tap below to ask a question or book a site visit."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
def merged_property(existing: dict | None, extraction: AnnouncementExtraction) -> dict:
    """The property as it will look after applying the announcement (without saving)."""
    prop = dict(existing or {"name": extraction.property_name})
    for key in PROPERTY_FIELDS:
        value = getattr(extraction, key)
        if value is not None and value != "":
            prop[key] = value
    return prop


DEFAULT_PROPERTY_IMAGE = "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80"


def apply_to_inventory(services: Any, extraction: AnnouncementExtraction) -> tuple[dict, bool]:
    repo = services.repo
    existing = repo.find_property_by_name(extraction.property_name)
    merged = merged_property(existing, extraction)
    changes = {k: merged[k] for k in PROPERTY_FIELDS if k in merged}
    if existing:
        return (repo.update_property(existing["id"], changes) if changes else existing), False
    if "image_url" not in changes or not changes.get("image_url"):
        changes["image_url"] = DEFAULT_PROPERTY_IMAGE
    return repo.insert_property({"name": extraction.property_name, **changes}), True


# ---------------------------------------------------------------------------
# Lead matching
# ---------------------------------------------------------------------------
def match_reasons(client: dict, prop: dict) -> list[str] | None:
    """Why this lead fits the property, or None if it doesn't (or we know nothing about their preferences)."""
    if client.get("status") == "CLOSED_BUYER":
        return None
    if prop.get("id") and client.get("interested_property_id") == prop.get("id"):
        return ["you asked about this property"]

    reasons: list[str] = []
    price = float(prop["price"]) if prop.get("price") is not None else None
    if client.get("budget_max") is not None and price is not None:
        if price > float(client["budget_max"]) * BUDGET_TOLERANCE:
            return None
        reasons.append("within your budget")
    if client.get("preferred_bedrooms") is not None and prop.get("bedrooms") is not None:
        if int(client["preferred_bedrooms"]) != int(prop["bedrooms"]):
            return None
        reasons.append(f"{prop['bedrooms']} bedrooms")
    if client.get("preferred_location") and prop.get("location"):
        pref, loc = client["preferred_location"].lower(), prop["location"].lower()
        if pref not in loc and loc not in pref:
            return None
        reasons.append(f"in {client['preferred_location']}")
    return reasons or None


def find_matching_leads(clients: list[dict], prop: dict) -> list[tuple[dict, list[str]]]:
    matches = []
    for client in clients:
        reasons = match_reasons(client, prop)
        if reasons:
            matches.append((client, reasons))
    return matches


def _reachable(client: dict) -> list[str]:
    return [c for c, ok in (("telegram", client.get("telegram_chat_id")), ("email", client.get("email"))) if ok]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def preview_announcement(services: Any, raw_text: str) -> dict:
    extraction = parse_announcement(services, raw_text)
    existing = services.repo.find_property_by_name(extraction.property_name)
    prop = merged_property(existing, extraction)
    ad_copy = generate_ad_copy(services, extraction, prop)
    matches = find_matching_leads(services.repo.list_clients(), prop)
    return {
        "parsed": extraction.model_dump(),
        "existing_property": bool(existing),
        "ad_copy": ad_copy,
        "matched_leads": [
            {"id": c["id"], "name": c.get("full_name") or c.get("telegram_username"), "reasons": r, "channels": _reachable(c)}
            for c, r in matches
        ],
    }


def publish_announcement(
    services: Any,
    raw_text: str,
    source: str = "portal",
    parsed: dict | None = None,
    ad_copy: str | None = None,
    post_to_channel: bool = True,
    notify_leads: bool = True,
) -> dict:
    settings = services.settings
    extraction = AnnouncementExtraction.model_validate(parsed) if parsed else parse_announcement(services, raw_text)
    prop, created = apply_to_inventory(services, extraction)
    record(
        services,
        "inventory_update",
        f"{'Added' if created else 'Updated'} {prop['name']} from {source} announcement ({extraction.announcement_type})",
        {"property_id": prop["id"], "parsed": extraction.model_dump()},
    )

    ad_copy = (ad_copy or "").strip() or generate_ad_copy(services, extraction, prop)

    channel_message_id = None
    channel_error = None
    if post_to_channel:
        try:
            tg = services.telegram
            buttons = [
                [{"text": "💬 Chat & Book Site Visit", "url": tg.deep_link(f"prop_{prop['id']}")}],
                [{"text": "💰 Request Payment Plan", "url": tg.deep_link(f"plan_{prop['id']}")}],
            ]
            message = tg.post_to_channel(ad_copy, buttons, prop.get("image_url"))
            channel_message_id = message.get("message_id")
            record(services, "ad_posted", f"Posted ad for {prop['name']} to the Telegram channel", {"message_id": channel_message_id})
        except Exception as exc:
            log.exception("channel post failed")
            channel_error = str(exc)
            record(services, "error", f"Channel post failed for {prop['name']}: {exc}")

    deliveries = []
    if notify_leads:
        for client, reasons in find_matching_leads(services.repo.list_clients(), prop):
            outcome = notify_client(services, client, **lead_message(settings, client, prop, extraction, reasons))
            deliveries.append({
                "client_id": client["id"],
                "name": client.get("full_name") or client_label(client),
                "reasons": reasons,
                **outcome,
            })
            record(
                services,
                "lead_broadcast",
                f"Sent {prop['name']} update to {client.get('full_name') or 'lead'}",
                {"reasons": reasons, **outcome},
                client["id"],
            )

    delivered = sum(1 for d in deliveries if "sent" in (d.get("telegram", ""), d.get("email", "")))
    announcement = services.repo.create_announcement(
        {
            "source": source,
            "raw_text": raw_text,
            "parsed": extraction.model_dump(),
            "ad_copy": ad_copy,
            "property_id": prop["id"],
            "channel_message_id": channel_message_id,
            "matched_count": delivered,
        }
    )
    return {
        "announcement_id": announcement["id"],
        "property": prop,
        "property_created": created,
        "ad_copy": ad_copy,
        "channel_message_id": channel_message_id,
        "channel_error": channel_error,
        "deliveries": deliveries,
        "delivered_count": delivered,
        "extraction": extraction.model_dump(),
    }


def lead_message(settings: Any, client: dict, prop: dict, extraction: AnnouncementExtraction, reasons: list[str]) -> dict:
    first_name = (client.get("full_name") or "").split(" ")[0] or "there"
    currency = settings.currency
    facts = [
        ("Property", prop["name"]),
        ("Location", prop.get("location") or "—"),
        ("Price", money(prop.get("price"), currency)),
        ("Bedrooms", str(prop.get("bedrooms") or "—")),
        ("Payment plan", prop.get("payment_plan") or "—"),
        ("Status", prop.get("construction_status") or "—"),
    ]
    why = ", ".join(reasons)
    text = "\n".join(
        [f"Hi {first_name}! 👋 Quick update from {settings.company_name}:", "", f"✨ {extraction.key_change}", ""]
        + [f"• {k}: {v}" for k, v in facts if v != "—"]
        + ["", f"We thought of you because it's {why}. Want to see it in person?"]
    )
    buttons = [
        [{"text": "📅 Book a site visit", "callback_data": f"visit:{prop['id']}"}],
        [{"text": "💬 Tell me more", "callback_data": f"prop:{prop['id']}"}],
    ]
    return {
        "text": text,
        "buttons": buttons,
        "email_subject": f"{prop['name']}: {extraction.key_change}"[:140],
        "email_title": f"Update on {prop['name']}",
        "email_html": paragraphs(f"Hi {first_name},\n\n{extraction.key_change}")
        + details_table(facts)
        + paragraphs(
            f"We're sharing this because it's {why}. Reply to our Telegram assistant or answer this email "
            f"to book a site visit.\n\n— {settings.agent_name}, {settings.company_name}"
        ),
    }


# ---------------------------------------------------------------------------
# Inbound email webhook payloads
# ---------------------------------------------------------------------------
def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", value)
    return html.unescape(re.sub(r"<[^>]+>", " ", value))


def email_payload_to_text(payload: dict) -> str:
    """Accept common inbound-email webhook shapes (Resend, Postmark, Mailgun, CloudMailin, Zapier...)."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    subject = data.get("subject") or data.get("Subject") or ""
    sender = data.get("from") or data.get("From") or ""
    if isinstance(sender, dict):
        sender = sender.get("email") or sender.get("address") or ""
    body = (
        data.get("text")
        or data.get("plain")
        or data.get("TextBody")
        or data.get("stripped-text")
        or data.get("body-plain")
        or data.get("body")
        or ""
    )
    if not body:
        raw_html = data.get("html") or data.get("HtmlBody") or data.get("body-html") or ""
        body = _strip_html(raw_html)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return f"From: {sender}\nSubject: {subject}\n\n{body}".strip()
