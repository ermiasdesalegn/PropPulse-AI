"""Supabase repository: every database read/write the app performs lives here."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, TypeVar

import httpx
from supabase import Client, create_client

log = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
)
try:
    import httpcore
    RETRYABLE_EXCEPTIONS += (
        httpcore.RemoteProtocolError,
        httpcore.ReadError,
        httpcore.ConnectError,
        httpcore.ConnectTimeout,
    )
except ImportError:
    pass


def retry_db(fn: Callable[[], T], max_retries: int = 2) -> T:
    """Execute a database operation with automatic backoff retry on transient connection drops."""
    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except RETRYABLE_EXCEPTIONS as exc:
            if attempt == max_retries:
                log.error("Supabase operation failed after %d retries: %s", max_retries, exc)
                raise
            log.warning("Supabase transient connection drop (%s) — retry %d/%d in %.1fs", exc, attempt + 1, max_retries, delay)
            time.sleep(delay)
            delay = min(delay * 2, 2.0)
    raise RuntimeError("unreachable")


APPOINTMENT_EMBED = "*, clients(*), properties(*)"
CONTRACT_EMBED = "*, clients(*), properties(*), installments(*)"
INSTALLMENT_EMBED = "*, contracts(*, clients(*), properties(*))"


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        out[key] = value
    return out


def _ts(value: datetime) -> str:
    """UTC 'Z' timestamp: avoids a literal '+' offset in PostgREST query strings."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


class Repo:
    def __init__(self, url: str, key: str):
        self.sb: Client = create_client(url, key)
        self._wrap_postgrest_retries()

    def _wrap_postgrest_retries(self) -> None:
        """Patch postgrest SyncQueryRequestBuilder.execute with automatic retries if not already patched."""
        try:
            from postgrest._sync.request_builder import SyncQueryRequestBuilder
            if not getattr(SyncQueryRequestBuilder, "_retry_wrapped", False):
                original_execute = SyncQueryRequestBuilder.execute

                def execute_with_retry(builder_self):
                    return retry_db(lambda: original_execute(builder_self))

                SyncQueryRequestBuilder.execute = execute_with_retry
                SyncQueryRequestBuilder._retry_wrapped = True
        except Exception as exc:
            log.warning("Could not patch SyncQueryRequestBuilder.execute: %s", exc)

    # -- clients -----------------------------------------------------------
    def get_client(self, client_id: str) -> dict | None:
        return _one(self.sb.table("clients").select("*").eq("id", client_id).limit(1).execute().data)

    def get_client_by_telegram(self, chat_id: int) -> dict | None:
        return _one(
            self.sb.table("clients").select("*").eq("telegram_chat_id", chat_id).limit(1).execute().data
        )

    def get_client_by_web_session(self, session_id: str) -> dict | None:
        return _one(
            self.sb.table("clients").select("*").eq("web_session_id", session_id).limit(1).execute().data
        )

    def create_client(self, data: dict) -> dict:
        return self.sb.table("clients").insert(_jsonable(data)).execute().data[0]

    def update_client(self, client_id: str, data: dict) -> dict:
        return self.sb.table("clients").update(_jsonable(data)).eq("id", client_id).execute().data[0]

    def list_clients(self, status: str | None = None, q: str | None = None) -> list[dict]:
        query = self.sb.table("clients").select("*, properties(name)").order("updated_at", desc=True)
        if status:
            query = query.eq("status", status)
        if q:
            safe = q.replace(",", " ").replace("(", " ").replace(")", " ")
            query = query.or_(
                f"full_name.ilike.*{safe}*,phone.ilike.*{safe}*,email.ilike.*{safe}*,"
                f"telegram_username.ilike.*{safe}*,preferred_location.ilike.*{safe}*"
            )
        return query.limit(500).execute().data

    # -- conversation log --------------------------------------------------
    def add_message(self, client_id: str, role: str, content: str, channel: str) -> None:
        self.sb.table("conversation_messages").insert(
            {"client_id": client_id, "role": role, "content": content, "channel": channel}
        ).execute()

    def recent_messages(self, client_id: str, limit: int = 20, roles: tuple[str, ...] | None = None) -> list[dict]:
        query = self.sb.table("conversation_messages").select("*").eq("client_id", client_id)
        if roles:
            query = query.in_("role", list(roles))
        rows = query.order("created_at", desc=True).order("id", desc=True).limit(limit).execute().data
        return list(reversed(rows))

    # -- properties --------------------------------------------------------
    def list_properties(self, available_only: bool = False) -> list[dict]:
        query = self.sb.table("properties").select("*").order("created_at", desc=True)
        if available_only:
            query = query.neq("status", "SOLD_OUT")
        return query.execute().data

    def get_property(self, property_id: str) -> dict | None:
        return _one(self.sb.table("properties").select("*").eq("id", property_id).limit(1).execute().data)

    def find_property_by_name(self, name: str) -> dict | None:
        # ilike without wildcards == case-insensitive equality (matches the lower(name) unique index)
        escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return _one(self.sb.table("properties").select("*").ilike("name", escaped).limit(1).execute().data)

    def insert_property(self, data: dict) -> dict:
        return self.sb.table("properties").insert(_jsonable(data)).execute().data[0]

    def update_property(self, property_id: str, data: dict) -> dict:
        return self.sb.table("properties").update(_jsonable(data)).eq("id", property_id).execute().data[0]

    # -- appointments ------------------------------------------------------
    def create_appointment(self, data: dict) -> dict:
        return self.sb.table("appointments").insert(_jsonable(data)).execute().data[0]

    def update_appointment(self, appointment_id: str, data: dict) -> dict:
        return self.sb.table("appointments").update(_jsonable(data)).eq("id", appointment_id).execute().data[0]

    def list_appointments(
        self, start_from: datetime | None = None, start_to: datetime | None = None, client_id: str | None = None
    ) -> list[dict]:
        query = self.sb.table("appointments").select(APPOINTMENT_EMBED).order("start_at")
        if start_from:
            query = query.gte("start_at", _ts(start_from))
        if start_to:
            query = query.lte("start_at", _ts(start_to))
        if client_id:
            query = query.eq("client_id", client_id)
        return query.limit(500).execute().data

    # -- contracts & installments -----------------------------------------
    def list_contracts(self, client_id: str | None = None) -> list[dict]:
        query = self.sb.table("contracts").select(CONTRACT_EMBED).order("created_at", desc=True)
        if client_id:
            query = query.eq("client_id", client_id)
        rows = query.execute().data
        for row in rows:
            row["installments"] = sorted(row.get("installments") or [], key=lambda i: i["sequence_no"])
        return rows

    def create_contract(self, data: dict) -> dict:
        return self.sb.table("contracts").insert(_jsonable(data)).execute().data[0]

    def create_installments(self, rows: list[dict]) -> list[dict]:
        return self.sb.table("installments").insert([_jsonable(r) for r in rows]).execute().data

    def pending_installments_due_by(self, due_by: date) -> list[dict]:
        return (
            self.sb.table("installments")
            .select(INSTALLMENT_EMBED)
            .eq("status", "PENDING")
            .lte("due_date", due_by.isoformat())
            .order("due_date")
            .execute()
            .data
        )

    def update_installment(self, installment_id: str, data: dict) -> dict:
        return self.sb.table("installments").update(_jsonable(data)).eq("id", installment_id).execute().data[0]

    # -- announcements -----------------------------------------------------
    def create_announcement(self, data: dict) -> dict:
        return self.sb.table("announcements").insert(_jsonable(data)).execute().data[0]

    def list_announcements(self, limit: int = 50) -> list[dict]:
        return (
            self.sb.table("announcements")
            .select("*, properties(name)")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )

    # -- activity feed -----------------------------------------------------
    def log_activity(self, kind: str, summary: str, payload: dict | None = None, client_id: str | None = None) -> None:
        self.sb.table("agent_activity").insert(
            {"kind": kind, "summary": summary, "payload": payload, "client_id": client_id}
        ).execute()

    def list_activity(self, limit: int = 50, kind: str | None = None, after_id: int | None = None) -> list[dict]:
        query = self.sb.table("agent_activity").select("*, clients(full_name, telegram_username)")
        if kind:
            query = query.eq("kind", kind)
        if after_id:
            query = query.gt("id", after_id)
        return query.order("id", desc=True).limit(limit).execute().data

    # -- stats -------------------------------------------------------------
    def count(self, table: str, **filters: Any) -> int:
        query = self.sb.table(table).select("id", count="exact").limit(1)
        for key, value in filters.items():
            query = query.eq(key, value)
        return query.execute().count or 0
