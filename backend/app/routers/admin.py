"""Dashboard API (Sales Command Center)."""

from __future__ import annotations

import calendar as cal
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_services
from app.notify import record
from app.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

ClientStatus = Literal["LEAD", "QUALIFIED", "SITE_VISIT_BOOKED", "CLOSED_BUYER"]


def _repo():
    return get_services().repo


# -- overview ---------------------------------------------------------------
@router.get("/integrations")
def integrations() -> dict:
    services = get_services()
    status = services.integration_status()
    bot_username = None
    if status["telegram"]:
        try:
            bot_username = services.telegram.bot_username
        except Exception:
            status["telegram"] = False
    return {
        "integrations": status,
        "bot_username": bot_username,
        "channel_id": services.settings.telegram_channel_id or None,
        "channel_link": "https://t.me/+3N90TiMJ79M2NTU0",
        "company_name": services.settings.company_name,
        "agent_name": services.settings.agent_name,
        "timezone": services.settings.timezone,
        "currency": services.settings.currency,
    }


@router.get("/stats")
def stats() -> dict:
    repo = _repo()
    settings = get_services().settings
    now = datetime.now(settings.tz)
    today = now.date()
    by_status = {s: repo.count("clients", status=s) for s in ("LEAD", "QUALIFIED", "SITE_VISIT_BOOKED", "CLOSED_BUYER")}
    upcoming = [a for a in repo.list_appointments(now, now + timedelta(days=7)) if a["status"] == "SCHEDULED"]
    due_soon = repo.pending_installments_due_by(today + timedelta(days=3))
    overdue = [i for i in due_soon if date.fromisoformat(i["due_date"]) < today]
    return {
        "clients_total": sum(by_status.values()),
        "clients_by_status": by_status,
        "properties_available": repo.count("properties", status="AVAILABLE"),
        "appointments_next_7_days": len(upcoming),
        "installments_due_soon": len(due_soon) - len(overdue),
        "installments_overdue": len(overdue),
        "overdue_amount": sum(float(i["amount"]) for i in overdue),
        "announcements_total": repo.count("announcements"),
    }


@router.get("/activity")
def activity(limit: int = 50, kind: str | None = None, after_id: int | None = None) -> list[dict]:
    return _repo().list_activity(min(limit, 200), kind, after_id)


# -- clients ----------------------------------------------------------------
class ClientIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    preferred_location: str | None = None
    preferred_bedrooms: int | None = None
    interested_property_id: str | None = None
    status: ClientStatus | None = None
    notes: str | None = None
    telegram_chat_id: int | None = None


@router.get("/clients")
def list_clients(status: str | None = None, q: str | None = None) -> list[dict]:
    return _repo().list_clients(status, q)


@router.post("/clients")
def create_client(body: ClientIn) -> dict:
    data = body.model_dump(exclude_none=True)
    data.setdefault("status", "LEAD")
    client = _repo().create_client(data)
    record(get_services(), "crm_update", f"Manually added {client.get('full_name') or 'client'} to the phonebook", None, client["id"])
    return client


@router.get("/clients/{client_id}")
def get_client(client_id: str) -> dict:
    repo = _repo()
    client = repo.get_client(client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    return {
        "client": client,
        "messages": repo.recent_messages(client_id, 200),
        "appointments": repo.list_appointments(client_id=client_id),
        "contracts": repo.list_contracts(client_id=client_id),
    }


@router.patch("/clients/{client_id}")
def update_client(client_id: str, body: ClientIn) -> dict:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "Nothing to update")
    return _repo().update_client(client_id, data)


# -- properties -------------------------------------------------------------
class PropertyIn(BaseModel):
    name: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    price: float | None = None
    price_per_sqm: float | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    down_payment: str | None = None
    payment_plan: str | None = None
    construction_status: str | None = None
    description: str | None = None
    floor_plan_url: str | None = None
    image_url: str | None = None
    status: Literal["AVAILABLE", "RESERVED", "SOLD_OUT"] | None = None


@router.get("/properties")
def list_properties() -> list[dict]:
    return _repo().list_properties()


@router.patch("/properties/{property_id}")
def update_property(property_id: str, body: PropertyIn) -> dict:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "Nothing to update")
    return _repo().update_property(property_id, data)


# -- appointments -----------------------------------------------------------
@router.get("/appointments")
def list_appointments(days_back: int = 7, days_ahead: int = 60) -> list[dict]:
    now = datetime.now(timezone.utc)
    return _repo().list_appointments(now - timedelta(days=days_back), now + timedelta(days=days_ahead))


class AppointmentPatch(BaseModel):
    status: Literal["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"]


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: str, body: AppointmentPatch) -> dict:
    return _repo().update_appointment(appointment_id, body.model_dump())


# -- buyer ledger -----------------------------------------------------------
class ContractIn(BaseModel):
    client_id: str
    property_id: str | None = None
    contract_number: str = Field(min_length=3)
    total_price: float = Field(gt=0)
    down_payment_amount: float | None = None
    monthly_installment: float = Field(gt=0)
    months: int = Field(ge=1, le=360)
    first_due_date: date
    bank_details: str | None = None


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, cal.monthrange(year, month)[1]))


@router.get("/contracts")
def list_contracts() -> list[dict]:
    return _repo().list_contracts()


@router.post("/contracts")
def create_contract(body: ContractIn) -> dict:
    repo = _repo()
    client = repo.get_client(body.client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    contract = repo.create_contract(
        body.model_dump(include={"client_id", "property_id", "contract_number", "total_price", "down_payment_amount", "monthly_installment", "bank_details"})
    )
    repo.create_installments(
        [
            {"contract_id": contract["id"], "sequence_no": n + 1, "due_date": add_months(body.first_due_date, n), "amount": body.monthly_installment}
            for n in range(body.months)
        ]
    )
    repo.update_client(client["id"], {"status": "CLOSED_BUYER"})
    record(
        get_services(),
        "contract_created",
        f"Contract {body.contract_number} created for {client.get('full_name') or 'client'} ({body.months} installments)",
        {"contract_id": contract["id"]},
        client["id"],
    )
    return contract


class InstallmentPatch(BaseModel):
    status: Literal["PENDING", "PAID"]


@router.patch("/installments/{installment_id}")
def update_installment(installment_id: str, body: InstallmentPatch) -> dict:
    paid_at = datetime.now(timezone.utc) if body.status == "PAID" else None
    return _repo().update_installment(installment_id, {"status": body.status, "paid_at": paid_at})


# -- announcements ----------------------------------------------------------
@router.get("/announcements")
def list_announcements() -> list[dict]:
    return _repo().list_announcements()
