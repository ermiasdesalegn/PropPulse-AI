import pytest
from fastapi.testclient import TestClient

import app.routers.admin as admin_router
import app.routers.chat as chat_router
import app.routers.cron as cron_router
import app.routers.telegram as telegram_router
from app.config import get_settings
from app.main import app
from tests.fakes import FakeGemini, make_services, text_response

ADMIN = {"X-Admin-Key": "admin-secret"}


@pytest.fixture
def services(monkeypatch):
    services = make_services()
    for module in (admin_router, chat_router, cron_router, telegram_router):
        monkeypatch.setattr(module, "get_services", lambda: services)
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_api_key", "admin-secret")
    monkeypatch.setattr(settings, "cron_secret", "cron-secret")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tg-secret")
    return services


@pytest.fixture
def client(services):
    return TestClient(app)


def test_admin_requires_key(client):
    assert client.get("/api/admin/clients").status_code == 401
    assert client.get("/api/admin/clients", headers=ADMIN).status_code == 200


def test_cron_accepts_cron_secret_or_admin_key(client):
    assert client.post("/api/cron/daily-proactive-run").status_code == 401
    r = client.post("/api/cron/daily-proactive-run", headers={"X-Cron-Secret": "cron-secret"})
    assert r.status_code == 200 and r.json()["trigger"] == "scheduler"
    assert client.post("/api/cron/daily-proactive-run", headers=ADMIN).json()["trigger"] == "dashboard"


def test_telegram_webhook_checks_secret(client, services):
    update = {"update_id": 1, "message": {"chat": {"id": 9, "type": "private"}, "from": {"id": 9}, "text": "/start"}}
    assert client.post("/api/telegram/webhook", json=update).status_code == 401
    assert client.post("/api/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "tg-secret"}).status_code == 200
    assert services.telegram.sent and services.telegram.sent[0]["chat_id"] == 9


def test_create_contract_generates_schedule_and_marks_buyer(client, services):
    buyer = services.repo.create_client({"full_name": "Yonas", "status": "QUALIFIED"})
    body = {
        "client_id": buyer["id"],
        "contract_number": "PP-9",
        "total_price": 3_600_000,
        "monthly_installment": 300_000,
        "months": 12,
        "first_due_date": "2026-01-31",
    }
    assert client.post("/api/admin/contracts", json=body, headers=ADMIN).status_code == 200
    contracts = client.get("/api/admin/contracts", headers=ADMIN).json()
    dues = [i["due_date"] for i in contracts[0]["installments"]]
    assert len(dues) == 12 and dues[:3] == ["2026-01-31", "2026-02-28", "2026-03-31"]
    assert services.repo.get_client(buyer["id"])["status"] == "CLOSED_BUYER"


def test_web_chat_roundtrip(client, services):
    services.gemini = FakeGemini([text_response("Hello! How can I help?")])
    r = client.post("/api/chat/web", json={"session_id": "abcdefgh123", "message": "hi"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["reply"] == "Hello! How can I help?"
    history = client.get("/api/chat/web/abcdefgh123", headers=ADMIN).json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
