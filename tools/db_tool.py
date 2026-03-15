"""
Read-only SQLite query executor.

Builds parameterized SQL from structured params extracted by the LLM.
Always appends a `merchant_id` filter so a merchant can never read
another merchant's data.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from db.database import SessionLocal  # noqa: E402
from security.validator import SQLValidationError, validate_sql  # noqa: E402

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _parse_date_filter(date_filter: str | None) -> tuple[datetime | None, datetime | None]:
    """
    Convert a natural-language date hint into a (start, end) datetime pair.

    Recognised hints (case-insensitive):
        "today", "yesterday", "last_7_days", "last_30_days",
        "this_month", "last_month", or an ISO date string "YYYY-MM-DD".
    """
    if not date_filter:
        return None, None

    now = datetime.utcnow()
    hint = date_filter.lower().strip()

    if hint == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif hint == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif hint in ("last_7_days", "last 7 days", "past week"):
        start = now - timedelta(days=7)
        end = now
    elif hint in ("last_30_days", "last 30 days", "past month"):
        start = now - timedelta(days=30)
        end = now
    elif hint in ("this_month", "this month"):
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif hint in ("last_month", "last month"):
        first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_this - timedelta(seconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Try ISO date
        try:
            date = datetime.strptime(hint[:10], "%Y-%m-%d")
            start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            return None, None

    return start, end


def build_query(merchant_id: str, sql_params: dict) -> tuple[str, dict[str, Any]]:
    """
    Build a parameterized SELECT query from *sql_params*.

    Parameters
    ----------
    merchant_id:
        The authenticated merchant — always added as a WHERE condition.
    sql_params:
        Dict with optional keys:
            - date_filter (str): natural-language date hint
            - status (str): "successful" | "failed" | "pending"
            - limit (int): max rows to return (capped at _MAX_LIMIT)
            - error_code (str): filter by specific error code

    Returns
    -------
    (sql_string, bind_params)
    """
    conditions = ["merchant_id = :merchant_id"]
    params: dict[str, Any] = {"merchant_id": merchant_id}

    status = sql_params.get("status")
    if status and status.lower() in ("successful", "failed", "pending"):
        conditions.append("status = :status")
        params["status"] = status.lower()

    error_code = sql_params.get("error_code")
    if error_code:
        conditions.append("error_code = :error_code")
        params["error_code"] = str(error_code)

    date_filter = sql_params.get("date_filter")
    start, end = _parse_date_filter(date_filter)
    if start:
        conditions.append("created_at >= :date_from")
        params["date_from"] = start
    if end:
        conditions.append("created_at <= :date_to")
        params["date_to"] = end

    limit = int(sql_params.get("limit") or _DEFAULT_LIMIT)
    limit = min(max(1, limit), _MAX_LIMIT)
    params["limit"] = limit

    where_clause = " AND ".join(conditions)
    sql = (
        "SELECT transaction_id, amount, currency, status, error_code, "
        "location, created_at "
        f"FROM transactions WHERE {where_clause} "
        "ORDER BY created_at DESC LIMIT :limit"
    )
    return sql, params


def query_database(merchant_id: str, sql_params: dict) -> list[dict[str, Any]]:
    """
    Execute a safe, merchant-scoped SELECT and return rows as dicts.

    Raises SQLValidationError if the generated query fails validation
    (this should never happen in normal operation but acts as a safeguard).
    """
    sql, params = build_query(merchant_id, sql_params)

    # Validate the generated SQL (defence-in-depth)
    validate_sql(sql)

    db = SessionLocal()
    try:
        result = db.execute(text(sql), params)
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            row_dict = dict(zip(columns, row))
            # Serialise datetime to ISO string for JSON compatibility
            if "created_at" in row_dict and isinstance(row_dict["created_at"], datetime):
                row_dict["created_at"] = row_dict["created_at"].isoformat()
            rows.append(row_dict)
        return rows
    finally:
        db.close()
