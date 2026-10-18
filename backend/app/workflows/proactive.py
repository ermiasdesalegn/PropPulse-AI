"""Workflow 3 — proactive meeting & post-sale installment reminders (daily cron)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.notify import fmt_dt, local_time, money, notify_client, record
from app.services.email import details_table, paragraphs

log = logging.getLogger(__name__)

APPOINTMENT_WINDOW = timedelta(hours=24)
INSTALLMENT_HORIZON_DAYS = 3

NOTICE_SYSTEM = (
    "You are {agent_name}, account executive at {company}. Write a short, warm but professional payment reminder "
    "for an existing home buyer (plain text, no Markdown, under 110 words). Include the installment amount, due date "
    "(or how many days overdue), contract number, and the bank details exactly as given. Thank them for being a "
    "valued owner. If overdue, be polite and ask them to share the payment receipt once paid."
)


# ---------------------------------------------------------------------------
# Selection (pure, unit-tested)
# ---------------------------------------------------------------------------
def select_appointments_for_reminder(appointments: list[dict], now: datetime) -> list[dict]:
    selected = []
    for appt in appointments:
        if appt.get("status") != "SCHEDULED" or appt.get("reminder_sent_at"):
            continue
        start = datetime.fromisoformat(appt["start_at"])
        if now <= start <= now + APPOINTMENT_WINDOW:
            selected.append(appt)
    return selected


def select_installments_for_reminder(installments: list[dict], today: date, tz) -> list[dict]:
    selected = []
    for inst in installments:
        if inst.get("status") != "PENDING":
            continue
        if date.fromisoformat(inst["due_date"]) > today + timedelta(days=INSTALLMENT_HORIZON_DAYS):
            continue
        client = (inst.get("contracts") or {}).get("clients") or {}
        if client.get("status") != "CLOSED_BUYER":
            continue
        if inst.get("last_reminded_at") and local_time(inst["last_reminded_at"], tz).date() == today:
            continue  # already reminded today
        selected.append(inst)
    return selected


def due_phrase(due: date, today: date) -> str:
    delta = (due - today).days
    if delta < 0:
        return f"overdue by {-delta} day{'s' if delta != -1 else ''}"
    if delta == 0:
        return "due today"
    return f"due in {delta} day{'s' if delta != 1 else ''}"


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------
def remind_appointment(services: Any, appt: dict) -> dict:
    settings = services.settings
    client = appt.get("clients") or {}
    prop = appt.get("properties") or {}
    when = fmt_dt(appt["start_at"], settings.tz)
    is_visit = appt["type"] == "SITE_VISIT"
    kind_label = "site visit" if is_visit else "phone consultation"
    first_name = (client.get("full_name") or "").split(" ")[0] or "there"

    rows = [("What", kind_label.capitalize()), ("When", when)]
    if prop.get("name"):
        rows.append(("Property", prop["name"]))
    if is_visit:
        rows.append(("Where", prop.get("location") or settings.sales_office_address))
    text = "\n".join(
        [f"⏰ Reminder, {first_name}: your {kind_label} is coming up!", ""]
        + [f"{k}: {v}" for k, v in rows]
        + ["", "Need to reschedule? Just reply here." + (" The location pin is below 👇" if is_visit else "")]
    )
    outcome = notify_client(
        services,
        client,
        text=text,
        location=(prop.get("latitude"), prop.get("longitude")) if is_visit else None,
        email_subject=f"Reminder: your {kind_label} on {when}",
        email_title=f"Your {kind_label} is coming up",
        email_html=paragraphs(f"Hi {first_name},\n\nThis is a friendly reminder of your upcoming appointment:")
        + details_table(rows)
        + paragraphs(f"See you soon!\n\n— {settings.agent_name}, {settings.company_name}"),
    )
    if "sent" in outcome.values():
        services.repo.update_appointment(appt["id"], {"reminder_sent_at": datetime.now(timezone.utc)})
    record(services, "appointment_reminder", f"Reminder for {kind_label} with {client.get('full_name') or 'client'} ({when})", outcome, client.get("id"))
    return {
        "appointment_id": appt["id"],
        "client": client.get("full_name"),
        "when": when,
        "kind": kind_label,
        "preview_text": text,
        "preview_email_subject": f"Reminder: your {kind_label} on {when}",
        "preview_email_html": (
            paragraphs(f"Hi {first_name},\n\nThis is a friendly reminder of your upcoming appointment:")
            + details_table(rows)
            + paragraphs(f"See you soon!\n\n— {settings.agent_name}, {settings.company_name}")
        ),
        **outcome,
    }


def installment_notice_text(services: Any, inst: dict, today: date) -> str:
    settings = services.settings
    contract = inst["contracts"]
    client = contract.get("clients") or {}
    prop = contract.get("properties") or {}
    due = date.fromisoformat(inst["due_date"])
    facts = (
        f"Buyer: {client.get('full_name')}\nProperty: {prop.get('name')}\nContract: {contract['contract_number']}\n"
        f"Installment #{inst['sequence_no']}: {money(inst['amount'], settings.currency)}\n"
        f"Due date: {due:%d %B %Y} ({due_phrase(due, today)})\nBank details: {contract.get('bank_details') or 'contact the sales office'}"
    )
    try:
        return services.gemini.text(
            facts, system=NOTICE_SYSTEM.format(agent_name=settings.agent_name, company=settings.company_name)
        ).replace("**", "")
    except Exception:
        log.exception("Gemini notice failed — using template")
        first_name = (client.get("full_name") or "").split(" ")[0] or "there"
        return (
            f"Dear {first_name},\n\nThis is a friendly reminder that installment #{inst['sequence_no']} of "
            f"{money(inst['amount'], settings.currency)} for contract {contract['contract_number']} ({prop.get('name')}) "
            f"is {due_phrase(due, today)} ({due:%d %B %Y}).\n\nPlease pay to: {contract.get('bank_details') or 'our sales office'}.\n\n"
            f"Thank you for being a valued {settings.company_name} home owner!"
        )


def remind_installment(services: Any, inst: dict, today: date) -> dict:
    settings = services.settings
    contract = inst["contracts"]
    client = contract.get("clients") or {}
    prop = contract.get("properties") or {}
    due = date.fromisoformat(inst["due_date"])
    status = due_phrase(due, today)

    notice = installment_notice_text(services, inst, today)
    invoice_rows = [
        ("Invoice for", client.get("full_name") or "—"),
        ("Contract", contract["contract_number"]),
        ("Property", prop.get("name") or "—"),
        ("Installment", f"#{inst['sequence_no']}"),
        ("Amount due", money(inst["amount"], settings.currency)),
        ("Due date", f"{due:%d %B %Y} ({status})"),
        ("Pay to", contract.get("bank_details") or settings.sales_office_address),
    ]
    outcome = notify_client(
        services,
        client,
        text=f"💳 Payment reminder\n\n{notice}",
        email_subject=f"Invoice: installment #{inst['sequence_no']} for {contract['contract_number']} — {status}",
        email_title=f"Installment #{inst['sequence_no']} — {status}",
        email_html=paragraphs(notice) + details_table(invoice_rows),
    )
    if "sent" in outcome.values():
        services.repo.update_installment(inst["id"], {"last_reminded_at": datetime.now(timezone.utc)})
    record(
        services,
        "installment_reminder",
        f"Installment #{inst['sequence_no']} reminder to {client.get('full_name') or 'buyer'} — {money(inst['amount'], settings.currency)} {status}",
        {"installment_id": inst["id"], **outcome},
        client.get("id"),
    )
    return {
        "installment_id": inst["id"],
        "client": client.get("full_name"),
        "contract": contract["contract_number"],
        "amount": inst["amount"],
        "due_date": inst["due_date"],
        "status": status,
        "preview_text": f"💳 Payment reminder\n\n{notice}",
        "preview_email_subject": f"Invoice: installment #{inst['sequence_no']} for {contract['contract_number']} — {status}",
        "preview_email_html": paragraphs(notice) + details_table(invoice_rows),
        **outcome,
    }


def run_daily_proactive(services: Any, now: datetime | None = None, trigger: str = "scheduler") -> dict:
    settings = services.settings
    now = now or datetime.now(settings.tz)
    today = now.astimezone(settings.tz).date()
    repo = services.repo

    appointments = select_appointments_for_reminder(repo.list_appointments(now, now + APPOINTMENT_WINDOW), now)
    installments = select_installments_for_reminder(
        repo.pending_installments_due_by(today + timedelta(days=INSTALLMENT_HORIZON_DAYS)), today, settings.tz
    )

    appointment_results, installment_results = [], []
    for appt in appointments:
        try:
            appointment_results.append(remind_appointment(services, appt))
        except Exception as exc:
            log.exception("appointment reminder failed")
            appointment_results.append({"appointment_id": appt["id"], "error": str(exc)})
    for inst in installments:
        try:
            installment_results.append(remind_installment(services, inst, today))
        except Exception as exc:
            log.exception("installment reminder failed")
            installment_results.append({"installment_id": inst["id"], "error": str(exc)})

    summary = {
        "ran_at": now.isoformat(),
        "trigger": trigger,
        "appointment_reminders": appointment_results,
        "installment_reminders": installment_results,
    }
    record(
        services,
        "cron_run",
        f"Daily proactive run ({trigger}): {len(appointment_results)} meeting reminder(s), "
        f"{len(installment_results)} installment reminder(s)",
        summary,
    )
    return summary
