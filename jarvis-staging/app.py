"""ORION JARVIS isolated staging (no model calls or personal data)."""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only presence flags are logged; never log a key or user content.
    log = logging.getLogger("uvicorn.error")
    log.info(
        "JARVIS_PREFLIGHT openai_key_present=%s supabase_secret_present=%s "
        "supabase_publishable_present=%s correct_supabase_project=%s ai_disabled=%s",
        bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        bool(os.environ.get("SUPABASE_SECRET_KEY", "").strip()),
        os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").startswith("sb_publishable_"),
        os.environ.get("SUPABASE_URL", "").rstrip("/") == "https://fdmfyguhpyiiyvjfimio.supabase.co",
        os.environ.get("ENABLE_MODEL_REQUESTS", "false").lower() != "true",
    )
    yield

app = FastAPI(title="ORION JARVIS staging", version="0.8.0-staging", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status":"ok","service":"orion-jarvis-api","stage":"isolated-staging","ai_enabled":False}

@app.get("/")
def index():
    return {"service":"ORION JARVIS","mode":"staging","message":"AI and personal-data endpoints are disabled until approved."}

@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail":"Not available in isolated staging"})
