"""
FastAPI application for the Omise merchant support chatbot.

Endpoints
---------
POST /chat   — main conversational endpoint (rate-limited)
GET  /health — liveness probe
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agent.graph import run_agent
from backend.schemas import ChatRequest, ChatResponse, HealthResponse
from vector_store.setup import setup_vector_store

# ---------------------------------------------------------------------------
# Rate limiter — keyed on merchant_id from the request body when available,
# otherwise falls back to IP address.
# ---------------------------------------------------------------------------


def _get_merchant_key(request: Request) -> str:
    """Extract merchant_id from the JSON body for rate-limit keying."""
    # body may not yet be parsed; fall back to IP
    merchant_id = getattr(request.state, "merchant_id", None)
    return merchant_id or get_remote_address(request)


limiter = Limiter(key_func=_get_merchant_key, default_limits=["10/minute"])

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Omise Merchant Support Chatbot",
    description="AI-powered support assistant for Omise merchants.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: initialise ChromaDB vector store (idempotent)
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    setup_vector_store(force=False)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Process a merchant support question through the LangGraph agent pipeline.

    Rate limit: 10 requests per minute per merchant_id.
    """
    # Stash merchant_id on request.state for the rate-limit key function
    request.state.merchant_id = body.merchant_id

    try:
        final_state = run_agent(
            question=body.question,
            merchant_id=body.merchant_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        merchant_id=body.merchant_id,
        question=final_state.get("user_question", body.question),
        intent=final_state.get("intent", "ambiguous"),
        confidence=final_state.get("confidence", 0.0),
        response=final_state.get("response", ""),
        db_results=final_state.get("db_results", []),
        retrieved_docs=final_state.get("retrieved_docs", []),
        sql_query=final_state.get("sql_query", ""),
        error=final_state.get("error", ""),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
