"""AfyaPlus triage app with versioned prompts - Week 8 face of the Week 6/7 API.

Same FastAPI agreement as weeks 6-7 (POST /triage, POST /token shape,
trace middleware), plus Deliverable 1:

  GET /health   -> now reports prompt_version, prompt SHA-256 (16-char),
                   model_version, mcp_server_version and release_tag.
  GET /pin      -> the full pin facts, for humans checking a rollout.

Run:
  uvicorn prompt_app:app --port 8000
  PROMPT_VERSION=1.3.0-candidate uvicorn prompt_app:app --port 8000
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import prompt_loader
import versions
from triage_stub import TriageRequest, TriageResponse, classify

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

APP_STARTED_AT = time.monotonic()
BUILD_SHA = os.getenv("BUILD_SHA", "dev")
SERVICE_NAME = os.getenv("SERVICE_NAME", "afyaplus-triage")

app = FastAPI(
    title="AfyaPlus Triage (versioned prompts)",
    version=versions.APP_VERSION,
    description="Week 8 capstone: same triage API, now prompt-versioned with a /health pin.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
    or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = request.headers.get("x-trace-id") or versions.sha256_text(
        f"{time.time()}:{id(request)}"
    )[:16]
    request.state.trace_id = tid
    response: Response = await call_next(request)
    response.headers["x-trace-id"] = tid
    return response


# ---------------------------------------------------------------------------
# /health - Deliverable 1 evidence: versions + prompt SHA at runtime
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    service: str
    status: str = "ok"
    app_version: str
    prompt_version: str
    prompt_sha256_16: str
    model_version: str
    mcp_server_version: str
    release_tag: str
    pinned_prompt_version: str
    candidate_rollout_percent: int = 0
    build_sha: str = "dev"
    uptime_seconds: float


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    facts = prompt_loader.health_facts()
    return HealthResponse(
        service=SERVICE_NAME,
        app_version=facts["app_version"],
        prompt_version=facts["prompt_version"],
        prompt_sha256_16=facts["prompt_sha256_16"],
        model_version=facts["model_version"],
        mcp_server_version=facts["mcp_server_version"],
        release_tag=facts["release_tag"],
        pinned_prompt_version=facts["pinned_prompt_version"],
        candidate_rollout_percent=facts["candidate_rollout_percent"],
        build_sha=BUILD_SHA,
        uptime_seconds=round(time.monotonic() - APP_STARTED_AT, 2),
    )


@app.get("/pin")
def pin() -> dict:
    return prompt_loader.health_facts()


# ---------------------------------------------------------------------------
# /triage - unchanged Week 6/7 contract, now prompt-version aware
# ---------------------------------------------------------------------------

class PromptedTriageResponse(TriageResponse):
    prompt_version: str = Field(..., description="Which prompt bundle answered.")
    prompt_sha256_16: str = Field(..., description="SHA-256 (16 chars) of that bundle.")


class SimpleTriageRequest(BaseModel):
    """Loose stand-in so external callers do not need the full EMR payload."""

    patient_id: str = Field(..., min_length=1, max_length=64)
    symptoms: list[str] = Field(..., min_length=1, max_length=12)
    age: int = Field(..., ge=0, le=120)
    heart_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    spo2: Optional[float] = None
    temperature_c: Optional[float] = None
    request_id: Optional[str] = None


def _to_full_request(simple: SimpleTriageRequest) -> TriageRequest:
    return TriageRequest(
        patient_id=simple.patient_id,
        symptoms=simple.symptoms,
        age=simple.age,
        sex="OTHER",
        heart_rate=simple.heart_rate,
        systolic_bp=simple.systolic_bp,
        spo2=simple.spo2,
        temperature_c=simple.temperature_c,
        request_id=simple.request_id,
    )


@app.post("/triage", response_model=PromptedTriageResponse)
def triage(body: SimpleTriageRequest, request: Request) -> PromptedTriageResponse:
    p = prompt_loader.load_prompt()
    result = classify(_to_full_request(body))
    return PromptedTriageResponse(
        **result.model_dump(),
        prompt_version=p["prompt_version"],
        prompt_sha256_16=p["prompt_sha256_16"],
    )
