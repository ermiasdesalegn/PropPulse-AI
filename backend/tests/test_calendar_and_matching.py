from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.agent.tools import filter_properties, is_qualified
from app.routers.admin import add_months
from app.services.calendar import compute_free_slots
from app.workflows.ingestion import email_payload_to_text, find_matching_leads, match_reasons

TZ = ZoneInfo("Africa/Addis_Ababa")
MONDAY = date(2026, 10, 19)


def slots(day_from, day_to, busy=(), now=None, minutes=60, limit=50):
    return compute_free_slots(
        day_from, day_to, list(busy), TZ, (9, 17), {0, 1, 2, 3, 4, 5}, minutes, now or datetime(2026, 10, 1, tzinfo=TZ), limit=limit
    )


def test_full_business_day_has_eight_hour_slots():
    result = slots(MONDAY, MONDAY)
    assert [s.hour for s in result] == [9, 10, 11, 12, 13, 14, 15, 16]


def test_busy_blocks_and_sundays_are_excluded():
    busy = [(datetime(2026, 10, 19, 10, 30, tzinfo=TZ), datetime(2026, 10, 19, 12, 0, tzinfo=TZ))]
    result = slots(MONDAY, MONDAY, busy)
    assert [s.hour for s in result] == [9, 12, 13, 14, 15, 16]
    assert slots(date(2026, 10, 25), date(2026, 10, 25)) == []  # Sunday


def test_slots_respect_minimum_lead_time():
    now = datetime(2026, 10, 19, 13, 15, tzinfo=TZ)
    result = slots(MONDAY, MONDAY, now=now, minutes=30)
    assert result[0] == datetime(2026, 10, 19, 14, 30, tzinfo=TZ)


def test_busy_blocks_in_other_timezones_are_respected():
    busy = [(datetime(2026, 10, 19, 6, 0, tzinfo=ZoneInfo("UTC")), datetime(2026, 10, 19, 7, 0, tzinfo=ZoneInfo("UTC")))]
    assert 9 not in [s.hour for s in slots(MONDAY, MONDAY, busy)]  # 06:00 UTC == 09:00 EAT


PROPS = [
    {"id": "a", "name": "Bole Skyline", "location": "Bole, Addis Ababa", "price": 9800000, "bedrooms": 2, "description": "rooftop gym"},
    {"id": "b", "name": "CMC Villas", "location": "CMC", "price": 21500000, "bedrooms": 4, "description": "private garden"},
]


def test_filter_properties():
    assert [p["id"] for p in filter_properties(PROPS, location="bole")] == ["a"]
    assert [p["id"] for p in filter_properties(PROPS, max_price=10_000_000)] == ["a"]
    assert [p["id"] for p in filter_properties(PROPS, bedrooms=4)] == ["b"]
    assert [p["id"] for p in filter_properties(PROPS, query="garden villa")] == ["b"]
    assert filter_properties(PROPS, location="Ayat") == []


def test_match_reasons():
    prop = {"id": "p1", "price": 9_800_000, "bedrooms": 2, "location": "Bole, Addis Ababa"}
    fits = {"budget_max": 9_000_000, "preferred_bedrooms": 2, "preferred_location": "Bole", "status": "QUALIFIED"}
    assert match_reasons(fits, prop) == ["within your budget", "2 bedrooms", "in Bole"]  # 9.8M is within 10% tolerance
    assert match_reasons({**fits, "budget_max": 5_000_000}, prop) is None
    assert match_reasons({**fits, "preferred_bedrooms": 3}, prop) is None
    assert match_reasons({**fits, "preferred_location": "CMC"}, prop) is None
    assert match_reasons({**fits, "status": "CLOSED_BUYER"}, prop) is None
    assert match_reasons({"status": "LEAD"}, prop) is None  # no known preferences → don't spam
    assert match_reasons({"status": "LEAD", "interested_property_id": "p1"}, prop) == ["you asked about this property"]
    assert len(find_matching_leads([fits, {"status": "LEAD"}], prop)) == 1


def test_is_qualified():
    assert not is_qualified({"full_name": "A"})
    assert is_qualified({"full_name": "A", "email": "a@b.co", "budget_max": 1})


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_email_payload_shapes():
    resend_style = {"type": "email.received", "data": {"from": "ceo@acme.com", "subject": "New units", "html": "<p>Price now <b>9M</b></p>"}}
    text = email_payload_to_text(resend_style)
    assert "Subject: New units" in text and "Price now" in text and "<b>" not in text
    postmark_style = {"From": "x@y.com", "Subject": "Promo", "TextBody": "10% off at Ayat"}
    assert "10% off at Ayat" in email_payload_to_text(postmark_style)
