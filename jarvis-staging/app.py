"""ORION JARVIS: safe, zero-provider staging entrypoint.

This staging process does not process personal data, call OpenAI, or
connect to privileged Supabase endpoints. It exists to validate Render
service isolation and connectivity before the reviewed API is deployed.
"""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="ORION JARVIS staging", version="0.8.0-staging")

@app.get("/health")
def health():
    return {"status": "ok", "service": "orion-jarvis-api", "stage": "isolated-staging", "ai_enabled": False}

@app.get("/")
def index():
    return {"service": "ORION JARVIS", "mode": "staging", "message": "AI and personal-data endpoints are disabled until approved."}

@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not available in isolated staging"})
