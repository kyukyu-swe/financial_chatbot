"""
SQL validator: only SELECT statements are allowed.
Blocks dangerous SQL keywords and patterns.
"""

import re

BLOCKED_PATTERNS = [
    r"\bDROP\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCREATE\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bREPLACE\b",
    r"\bMERGE\b",
    r"--",          # SQL line comment
    r";",           # statement terminator (second statement injection)
    r"/\*",         # block comment open
    r"\*/",         # block comment close
    r"\bUNION\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
]

_BLOCKED_RE = re.compile(
    "|".join(BLOCKED_PATTERNS),
    re.IGNORECASE,
)


class SQLValidationError(ValueError):
    """Raised when a SQL query fails validation."""


def validate_sql(query: str) -> str:
    """
    Validate that *query* is a safe, read-only SELECT statement.

    Returns the stripped query if valid, raises SQLValidationError otherwise.
    """
    if not isinstance(query, str):
        raise SQLValidationError("Query must be a string.")

    stripped = query.strip()

    if not stripped:
        raise SQLValidationError("Query is empty.")

    # Must start with SELECT
    if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        raise SQLValidationError(
            "Only SELECT statements are permitted. "
            f"Got: '{stripped[:40]}...'"
        )

    # Block dangerous patterns
    match = _BLOCKED_RE.search(stripped)
    if match:
        raise SQLValidationError(
            f"Forbidden pattern detected in SQL query: '{match.group()}'"
        )

    return stripped
