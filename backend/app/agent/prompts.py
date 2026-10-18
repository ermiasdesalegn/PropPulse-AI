from __future__ import annotations

from datetime import datetime

from app.notify import fmt_dt, money

SYSTEM_TEMPLATE = """You are {agent_name}, the AI sales & account executive for {company}, a real estate developer.
You chat with prospective and existing clients on {channel_label}.

Today is {today} ({timezone}). Prices are in {currency}. Sales office: {office}.

GOALS (in order)
1. Answer property questions accurately — ALWAYS call search_properties for prices, sizes, floor plans,
   payment plans, down payments or construction status. Never invent numbers or properties.
2. Qualify the lead naturally: full name, phone or email, budget, preferred location, bedrooms.
   Ask at most one or two questions per message, woven into helpful answers — never an interrogation.
3. Whenever the client shares any of those details, IMMEDIATELY call upsert_client_profile with just those fields.
4. Move qualified leads toward a phone consultation or an in-person site visit:
   call check_calendar_availability, offer 2-3 concrete slots, and only after the client picks one,
   call book_appointment with that slot's exact start_iso.

STYLE
- Warm, confident, concise (usually under 120 words). Plain text only — no Markdown, no asterisks.
- Use a few tasteful emojis at most. Use line breaks for lists.
- Reply in the client's language (English, Amharic, etc.).
- Mention times in {timezone} local time in a friendly format.
- If a tool returns an error, recover gracefully (ask for missing info or offer alternatives).
- If asked something you cannot answer (legal advice, things not in inventory), say a human colleague will follow up.

CLIENT PROFILE (from CRM)
{profile}
{extra}"""


def _profile_block(client: dict, currency: str) -> str:
    def val(key: str) -> str:
        v = client.get(key)
        return "unknown" if v in (None, "") else str(v)

    budget = "unknown"
    if client.get("budget_min") is not None or client.get("budget_max") is not None:
        budget = f"{money(client.get('budget_min'), currency)} – {money(client.get('budget_max'), currency)}"
    return "\n".join(
        [
            f"- Status: {val('status')}",
            f"- Name: {val('full_name')}",
            f"- Phone: {val('phone')}",
            f"- Email: {val('email')}",
            f"- Telegram: {'@' + client['telegram_username'] if client.get('telegram_username') else 'unknown'}",
            f"- Budget: {budget}",
            f"- Preferred location: {val('preferred_location')}",
            f"- Preferred bedrooms: {val('preferred_bedrooms')}",
            f"- Interested property id: {val('interested_property_id')}",
            f"- Notes: {val('notes')}",
        ]
    )


def build_system_prompt(
    settings,
    client: dict,
    channel: str,
    now: datetime,
    interested_property: dict | None = None,
    upcoming_appointments: list[dict] | None = None,
    contracts: list[dict] | None = None,
) -> str:
    tz, currency = settings.tz, settings.currency
    extra: list[str] = []
    if interested_property:
        extra.append(
            f"\nThe client is currently interested in: {interested_property['name']} "
            f"(id {interested_property['id']}, {interested_property.get('location')}, "
            f"{money(interested_property.get('price'), currency)})."
        )
    if upcoming_appointments:
        extra.append("\nUPCOMING APPOINTMENTS")
        for a in upcoming_appointments:
            prop = (a.get("properties") or {}).get("name")
            extra.append(f"- {a['type']} on {fmt_dt(a['start_at'], tz)}" + (f" at {prop}" if prop else ""))
    if contracts:
        extra.append("\nBUYER CONTRACTS (this client is an existing buyer)")
        for c in contracts:
            pending = [i for i in c.get("installments", []) if i["status"] == "PENDING"]
            nxt = pending[0] if pending else None
            extra.append(
                f"- Contract {c['contract_number']} for {(c.get('properties') or {}).get('name', 'property')}: "
                f"monthly installment {money(c['monthly_installment'], currency)}; "
                + (f"next due {nxt['due_date']} ({money(nxt['amount'], currency)})" if nxt else "fully paid")
                + (f"; pay to: {c['bank_details']}" if c.get("bank_details") else "")
            )
    return SYSTEM_TEMPLATE.format(
        agent_name=settings.agent_name,
        company=settings.company_name,
        channel_label="Telegram" if channel == "telegram" else "the company website chat",
        today=now.strftime("%A %d %B %Y, %I:%M %p"),
        timezone=settings.timezone,
        currency=currency,
        office=settings.sales_office_address,
        profile=_profile_block(client, currency),
        extra="\n".join(extra),
    )
