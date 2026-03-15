"""
Pydantic request/response models for the FastAPI backend.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The merchant's natural-language question.",
    )
    merchant_id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="The authenticated merchant identifier, e.g. 'mch_001'.",
    )

    @field_validator("merchant_id")
    @classmethod
    def merchant_id_alphanumeric(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "merchant_id must contain only letters, digits, underscores, or hyphens."
            )
        return v


class ChatResponse(BaseModel):
    merchant_id: str = Field(..., description="Echo of the request merchant_id.")
    question: str = Field(..., description="The (sanitised) question that was answered.")
    intent: str = Field(..., description="Classified intent: transaction | api_docs | ambiguous.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent classification confidence.")
    response: str = Field(..., description="The generated natural-language answer.")
    db_results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Transaction rows returned from the database (empty for api_docs intent).",
    )
    retrieved_docs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="API doc chunks retrieved from ChromaDB (empty for transaction-only intent).",
    )
    sql_query: str = Field(
        default="",
        description="The parameterized SQL query that was executed (for transparency).",
    )
    error: str = Field(
        default="",
        description="Non-empty if an error occurred during processing.",
    )


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
