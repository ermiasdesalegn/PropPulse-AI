import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.deps import NotConfigured
from app.routers import admin, chat, cron, ingest, telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("proppulse")

settings = get_settings()
if not settings.admin_api_key:
    log.warning("ADMIN_API_KEY is not set — admin endpoints are UNPROTECTED (fine for local dev only)")

app = FastAPI(title="PropPulse AI", version="1.0.0", description="Autonomous real estate sales & client lifecycle agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (telegram.router, ingest.router, cron.router, chat.router, admin.router):
    app.include_router(router)


@app.exception_handler(NotConfigured)
def not_configured_handler(_: Request, exc: NotConfigured) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
