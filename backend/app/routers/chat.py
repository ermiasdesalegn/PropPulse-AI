from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import get_services
from app.security import require_admin
from app.workflows.conversation import handle_web_message

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(require_admin)])


class WebMessage(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


@router.post("/web")
def web_chat(body: WebMessage) -> dict:
    return handle_web_message(get_services(), body.session_id, body.message.strip())


@router.get("/web/{session_id}")
def web_history(session_id: str) -> dict:
    repo = get_services().repo
    client = repo.get_client_by_web_session(session_id)
    if not client:
        return {"client": None, "messages": []}
    return {"client": client, "messages": repo.recent_messages(client["id"], 100)}
