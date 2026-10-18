from fastapi import APIRouter, Depends, Header

from app.deps import get_services
from app.security import require_cron
from app.workflows.proactive import run_daily_proactive

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.post("/daily-proactive-run", dependencies=[Depends(require_cron)])
def daily_proactive_run(x_cron_secret: str | None = Header(default=None)) -> dict:
    return run_daily_proactive(get_services(), trigger="scheduler" if x_cron_secret else "dashboard")
