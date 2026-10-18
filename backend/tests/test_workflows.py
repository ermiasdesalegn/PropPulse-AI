from datetime import date, datetime, timedelta, timezone

from app.agent.runner import run_agent
from app.agent.tools import AgentContext, book_appointment
from app.workflows.conversation import handle_telegram_update, handle_web_message
from app.workflows.ingestion import publish_announcement
from app.workflows.proactive import run_daily_proactive, select_installments_for_reminder
from tests.fakes import FakeGemini, function_call_response, make_services, text_response


def seed_property(services, **extra):
    return services.repo.insert_property(
        {"name": "Bole Skyline", "location": "Bole, Addis Ababa", "price": 9_800_000, "bedrooms": 2, "latitude": 8.99, "longitude": 38.78, **extra}
    )


# ---------------------------------------------------------------------------
# Workflow 2 — conversation / agent
# ---------------------------------------------------------------------------
def test_agent_loop_executes_tools_and_persists_profile():
    services = make_services()
    seed_property(services)
    services.gemini = FakeGemini(
        [
            function_call_response(
                ("upsert_client_profile", {"full_name": "Selam T", "email": "selam@example.org", "budget_max": 10_000_000}),
                ("search_properties", {"location": "Bole"}),
            ),
            text_response("Great news Selam! Bole Skyline is ETB 9,800,000."),
        ]
    )
    result = handle_web_message(services, "session-12345", "Hi, I'm Selam, selam@example.org, budget 10M, looking in Bole")

    assert result["reply"].startswith("Great news")
    assert [c["name"] for c in result["tool_calls"]] == ["upsert_client_profile", "search_properties"]
    assert result["tool_calls"][1]["result"]["results"][0]["name"] == "Bole Skyline"
    client = services.repo.get_client_by_web_session("session-12345")
    assert client["full_name"] == "Selam T" and client["status"] == "QUALIFIED"
    roles = [m["role"] for m in services.repo.messages]
    assert roles == ["user", "tool", "tool", "assistant"]
    # second Gemini request carried the model's function call + our function responses
    contents, _ = services.gemini.requests[1]
    assert [c.role for c in contents] == ["user", "model", "user"]


def test_agent_history_is_replayed():
    services = make_services()
    client = services.repo.create_client({"web_session_id": "s" * 10})
    services.repo.add_message(client["id"], "assistant", "Welcome!", "web")  # leading model turn is dropped
    services.repo.add_message(client["id"], "user", "hello", "web")
    services.repo.add_message(client["id"], "assistant", "Hi! How can I help?", "web")
    services.gemini = FakeGemini([text_response("Sure.")])
    run_agent(services, client, "show me 2 bedrooms", "web")
    contents, config = services.gemini.requests[0]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert "Acme Homes" in config.system_instruction


def test_telegram_start_deep_link_sets_interest_and_replies():
    services = make_services()
    prop = seed_property(services)
    services.gemini = FakeGemini([text_response("Bole Skyline is a 2-bedroom gem!")])
    update = {
        "update_id": 1,
        "message": {"chat": {"id": 555, "type": "private"}, "from": {"id": 555, "username": "selam", "first_name": "Selam"}, "text": f"/start prop_{prop['id']}"},
    }
    handle_telegram_update(services, update)

    client = services.repo.get_client_by_telegram(555)
    assert client["interested_property_id"] == prop["id"]
    sent = services.telegram.sent[-1]
    assert sent["chat_id"] == 555
    assert "Bole Skyline" in sent["text"]
    assert "Hi Selam!" in sent["text"]
    assert sent["buttons"] == [
        [
            {"text": "📅 Book Site Visit", "callback_data": f"visit:{prop['id']}"},
            {"text": "📞 Schedule Telegram Call", "callback_data": f"call:{prop['id']}"},
        ]
    ]


def test_plain_start_sends_menu_without_calling_gemini():
    services = make_services()
    handle_telegram_update(services, {"update_id": 2, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "/start"}})
    assert services.telegram.sent[0]["buttons"] is not None
    assert services.gemini.requests == []


def test_telegram_start_plan_deep_link_presents_financing():
    services = make_services()
    prop = seed_property(services)
    update = {
        "update_id": 2,
        "message": {"chat": {"id": 777, "type": "private"}, "from": {"id": 777, "username": "dawit", "first_name": "Dawit"}, "text": f"/start plan_{prop['id']}"},
    }
    handle_telegram_update(services, update)

    client = services.repo.get_client_by_telegram(777)
    assert client["interested_property_id"] == prop["id"]
    sent = services.telegram.sent[-1]
    assert "Dawit" in sent["text"]
    assert "financing & payment plan" in sent["text"]
    assert sent["buttons"][0][0]["text"] == "📅 Book Site Visit"
    assert sent["buttons"][0][1]["text"] == "📞 Schedule Telegram Call"


def test_telegram_callback_triggers_agent():
    services = make_services()
    prop = seed_property(services)
    services.gemini = FakeGemini([text_response("I would be delighted to schedule a site visit for you!")])
    update = {
        "update_id": 3,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 888, "first_name": "Hanna"},
            "message": {"chat": {"id": 888, "type": "private"}},
            "data": f"visit:{prop['id']}",
        },
    }
    handle_telegram_update(services, update)
    assert services.telegram.sent[-1]["text"] == "I would be delighted to schedule a site visit for you!"


def test_book_appointment_creates_event_and_notifies():
    services = make_services()
    prop = seed_property(services)
    client = services.repo.create_client(
        {"full_name": "Selam T", "phone": "+251911", "email": "selam@example.org", "telegram_chat_id": 555, "budget_max": 1e7, "status": "QUALIFIED"}
    )
    now = datetime(2026, 10, 19, 8, 0, tzinfo=services.settings.tz)
    ctx = AgentContext(services=services, client=client, channel="telegram", now=now)
    start = datetime(2026, 10, 20, 10, 0, tzinfo=services.settings.tz)

    result = book_appointment(ctx, start_iso=start.isoformat(), appointment_type="SITE_VISIT", property_id=prop["id"])

    assert result["booked"] and result["calendar_synced"]
    assert result["confirmation_sent"] == {"telegram": "sent", "email": "sent"}
    assert services.telegram.locations == [(555, 8.99, 38.78)]
    assert services.repo.get_client(client["id"])["status"] == "SITE_VISIT_BOOKED"
    # the same slot can't be double-booked
    again = book_appointment(ctx, start_iso=start.isoformat(), appointment_type="SITE_VISIT", property_id=prop["id"])
    assert "taken" in again["error"]


def test_book_appointment_requires_contact_details():
    services = make_services()
    client = services.repo.create_client({"telegram_chat_id": 1})
    ctx = AgentContext(services=services, client=client, channel="telegram")
    assert "full name" in book_appointment(ctx, start_iso="2030-01-01T10:00:00+03:00", appointment_type="PHONE_CALL")["error"]


# ---------------------------------------------------------------------------
# Workflow 1 — ingestion & broadcast
# ---------------------------------------------------------------------------
def test_publish_announcement_updates_inventory_posts_ad_and_targets_leads():
    services = make_services()
    existing = seed_property(services)
    repo = services.repo
    match = repo.create_client({"full_name": "Selam T", "telegram_chat_id": 555, "email": "s@example.org", "budget_max": 9_000_000, "preferred_bedrooms": 2, "status": "QUALIFIED"})
    repo.create_client({"full_name": "Too Poor", "telegram_chat_id": 556, "budget_max": 3_000_000, "status": "QUALIFIED"})
    repo.create_client({"full_name": "Buyer", "telegram_chat_id": 557, "budget_max": 20_000_000, "status": "CLOSED_BUYER"})

    parsed = {"announcement_type": "PRICE_UPDATE", "property_name": "bole skyline", "price": 9_200_000, "key_change": "Bole Skyline price drops to ETB 9.2M"}
    result = publish_announcement(services, "Price drop!", parsed=parsed, ad_copy="🔥 Price drop at Bole Skyline")

    assert not result["property_created"]
    assert repo.get_property(existing["id"])["price"] == 9_200_000
    post = services.telegram.channel_posts[0]
    assert post["text"] == "🔥 Price drop at Bole Skyline"
    assert post["buttons"][0][0]["url"] == f"https://t.me/acme_bot?start=prop_{existing['id']}"
    assert [d["client_id"] for d in result["deliveries"]] == [match["id"]]
    assert result["delivered_count"] == 1
    assert services.mailer.sent[0]["to"] == "s@example.org"
    assert repo.announcements[0]["matched_count"] == 1


def test_publish_announcement_creates_new_property():
    services = make_services()
    parsed = {"announcement_type": "NEW_LISTING", "property_name": "Ayat Heights", "location": "Ayat", "price": 5_000_000, "bedrooms": 3, "key_change": "New Ayat Heights launch"}
    result = publish_announcement(services, "New project", parsed=parsed, ad_copy="New!", notify_leads=False)
    assert result["property_created"]
    assert services.repo.find_property_by_name("Ayat Heights")["bedrooms"] == 3


# ---------------------------------------------------------------------------
# Workflow 3 — proactive reminders
# ---------------------------------------------------------------------------
def seed_ledger(services, due_offsets):
    repo = services.repo
    buyer = repo.create_client({"full_name": "Yonas A", "telegram_chat_id": 900, "email": "y@example.org", "status": "CLOSED_BUYER"})
    prop = seed_property(services)
    contract = repo.create_contract(
        {"client_id": buyer["id"], "property_id": prop["id"], "contract_number": "PP-1", "total_price": 1, "monthly_installment": 300000, "bank_details": "CBE 1000"}
    )
    today = datetime.now(services.settings.tz).date()
    repo.create_installments(
        [{"contract_id": contract["id"], "sequence_no": n, "due_date": today + timedelta(days=off), "amount": 300000} for n, off in enumerate(due_offsets, 1)]
    )
    return buyer, prop


def test_daily_run_sends_reminders_once():
    services = make_services()
    services.gemini = FakeGemini(text_reply="Dear Yonas, installment due. Pay to CBE 1000.")
    buyer, prop = seed_ledger(services, due_offsets=[-2, 2, 10])
    lead = services.repo.create_client({"full_name": "Selam", "telegram_chat_id": 555, "status": "SITE_VISIT_BOOKED"})
    now = datetime.now(timezone.utc)
    services.repo.create_appointment(
        {"client_id": lead["id"], "property_id": prop["id"], "type": "SITE_VISIT", "start_at": now + timedelta(hours=5), "end_at": now + timedelta(hours=6)}
    )
    services.repo.create_appointment(  # outside the 24h window
        {"client_id": lead["id"], "property_id": prop["id"], "type": "PHONE_CALL", "start_at": now + timedelta(days=3), "end_at": now + timedelta(days=3, hours=1)}
    )

    first = run_daily_proactive(services, trigger="test")
    assert len(first["appointment_reminders"]) == 1
    assert first["appointment_reminders"][0]["telegram"] == "sent"
    statuses = sorted(r["status"] for r in first["installment_reminders"])
    assert statuses == ["due in 2 days", "overdue by 2 days"]
    assert all(r["telegram"] == "sent" and r["email"] == "sent" for r in first["installment_reminders"])
    assert "Invoice" in services.mailer.sent[-1]["subject"]

    second = run_daily_proactive(services, trigger="test")
    assert second["appointment_reminders"] == [] and second["installment_reminders"] == []


def test_installment_selection_skips_non_buyers_and_paid():
    today = date(2026, 10, 19)
    base = {"status": "PENDING", "due_date": "2026-10-20", "last_reminded_at": None, "contracts": {"clients": {"status": "CLOSED_BUYER"}}}
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Africa/Addis_Ababa")
    assert len(select_installments_for_reminder([base], today, tz)) == 1
    assert select_installments_for_reminder([{**base, "status": "PAID"}], today, tz) == []
    assert select_installments_for_reminder([{**base, "contracts": {"clients": {"status": "LEAD"}}}], today, tz) == []
    assert select_installments_for_reminder([{**base, "due_date": "2026-10-25"}], today, tz) == []


def test_booking_detects_overlap_with_meeting_that_started_earlier():
    services = make_services()
    tz = services.settings.tz
    client = services.repo.create_client({"full_name": "A", "phone": "1", "status": "QUALIFIED"})
    services.repo.create_appointment(
        {"client_id": client["id"], "type": "SITE_VISIT", "start_at": datetime(2026, 10, 20, 9, 30, tzinfo=tz), "end_at": datetime(2026, 10, 20, 10, 30, tzinfo=tz)}
    )
    ctx = AgentContext(services=services, client=client, channel="web", now=datetime(2026, 10, 19, 8, 0, tzinfo=tz))
    result = book_appointment(ctx, start_iso=datetime(2026, 10, 20, 10, 0, tzinfo=tz).isoformat(), appointment_type="PHONE_CALL")
    assert "taken" in result["error"]
