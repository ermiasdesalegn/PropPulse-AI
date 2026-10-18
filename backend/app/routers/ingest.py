from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_services
from app.security import require_admin, require_ingest_token
from app.workflows.ingestion import email_payload_to_text, preview_announcement, publish_announcement

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class AnnouncementIn(BaseModel):
    raw_text: str = Field(min_length=10)
    parsed: dict | None = None
    ad_copy: str | None = None
    post_to_channel: bool = True
    notify_leads: bool = True


class PreviewIn(BaseModel):
    raw_text: str = Field(min_length=10)


@router.post("/announcement/preview", dependencies=[Depends(require_admin)])
def preview(body: PreviewIn) -> dict:
    return preview_announcement(get_services(), body.raw_text)


@router.post("/announcement", dependencies=[Depends(require_admin)])
def publish(body: AnnouncementIn) -> dict:
    return publish_announcement(
        get_services(),
        body.raw_text,
        source="portal",
        parsed=body.parsed,
        ad_copy=body.ad_copy,
        post_to_channel=body.post_to_channel,
        notify_leads=body.notify_leads,
    )


@router.post("/email-webhook", dependencies=[Depends(require_ingest_token)])
def email_webhook(payload: dict) -> dict:
    text = email_payload_to_text(payload)
    if len(text) < 20:
        raise HTTPException(status_code=422, detail="Email payload has no readable content")
    result = publish_announcement(get_services(), text, source="email")
    return {"announcement_id": result["announcement_id"], "property": result["property"]["name"], "delivered": result["delivered_count"]}
