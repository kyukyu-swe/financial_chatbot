"""
Input sanitizer: strips prompt-injection patterns and enforces length limits.
"""

import re

MAX_INPUT_LENGTH = 500

# Patterns commonly used in prompt-injection attacks
_INJECTION_PATTERNS = [
    # Role / persona overrides
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?previous\s+instructions?",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"roleplay\s+as\s+",
    r"jailbreak",
    # Direct instruction injection
    r"new\s+instructions?:",
    r"system\s*:",
    r"<\s*system\s*>",
    r"<\s*/\s*system\s*>",
    r"\[system\]",
    r"\[user\]",
    r"\[assistant\]",
    r"<\s*\|?\s*im_start\s*\|?\s*>",
    r"<\s*\|?\s*im_end\s*\|?\s*>",
    # Data exfiltration / leakage attempts
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"show\s+(me\s+)?(your\s+)?(internal|system|secret)",
    r"what\s+are\s+your\s+instructions",
    r"repeat\s+(everything|the\s+above|all)\s+(above|back)",
    # Shell / code execution
    r"```\s*(bash|sh|python|js|javascript|ruby|php)",
    r"os\.system\s*\(",
    r"subprocess\s*\.",
    r"eval\s*\(",
    r"exec\s*\(",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

# Characters that have no place in natural-language merchant queries
_SUSPICIOUS_CHARS_RE = re.compile(r"[<>{}\[\]\\|`]")


def sanitize_input(text: str) -> str:
    """
    Clean and validate user input.

    Steps:
    1. Enforce maximum length (truncate to MAX_INPUT_LENGTH).
    2. Strip leading/trailing whitespace.
    3. Remove characters that are suspicious in a chat context.
    4. Remove prompt-injection patterns.
    5. Collapse excessive whitespace.

    Returns the sanitized string.
    """
    if not isinstance(text, str):
        text = str(text)

    # 1. Length cap
    text = text[:MAX_INPUT_LENGTH]

    # 2. Strip whitespace
    text = text.strip()

    # 3. Remove suspicious characters
    text = _SUSPICIOUS_CHARS_RE.sub("", text)

    # 4. Remove injection patterns (replace with space to avoid word merging)
    text = _INJECTION_RE.sub(" ", text)

    # 5. Collapse multiple spaces / newlines
    text = re.sub(r"\s+", " ", text).strip()

    return text
