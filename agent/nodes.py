"""
All 7 LangGraph node functions for the Omise merchant support agent.

Nodes (in execution order):
    1. sanitize_input       – clean user input
    2. classify_intent      – determine question type
    3. extract_sql_params   – extract structured DB query params
    4. query_database       – execute safe, merchant-scoped SQL
    5. search_docs          – vector-search Omise API docs
    6. generate_response    – call LLM to compose final answer
    7. filter_output        – strip any sensitive data before returning
"""

from __future__ import annotations

import json
import os
import re
import sys

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from agent.state import AgentState  # noqa: E402
from security.sanitizer import sanitize_input as _sanitize  # noqa: E402
from tools.db_tool import build_query, query_database as _query_db  # noqa: E402
from tools.docs_tool import search_docs as _search_docs  # noqa: E402

# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


def _get_llm():
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=OPENAI_MODEL, temperature=0)
    else:
        from langchain_ollama import ChatOllama

        return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL, temperature=0)


# ---------------------------------------------------------------------------
# Node 1 – sanitize_input
# ---------------------------------------------------------------------------


def sanitize_input(state: AgentState) -> AgentState:
    """Strip injection patterns and enforce length limits on the raw question."""
    raw = state.get("user_question", "")
    cleaned = _sanitize(raw)
    return {**state, "user_question": cleaned, "error": ""}


# ---------------------------------------------------------------------------
# Node 2 – classify_intent
# ---------------------------------------------------------------------------

# --- Rule-based pre-classifier -------------------------------------------
# These patterns are checked BEFORE the LLM to avoid misclassification by
# small models (e.g. gemma3:1b). A question like "What does error 402 mean?"
# should never be routed to the transaction DB.

_API_DOCS_PATTERNS = re.compile(
    r"""
    what\s+does\s+error           # "what does error X mean"
    | what\s+is\s+error           # "what is error X"
    | error\s+[45]\d{2}           # "error 401/402/422/500"
    | (explain|describe)\s+error  # "explain error 402"
    | how\s+do\s+i\s+(refund|process\s+a\s+refund|set\s+up|setup|create\s+a\s+charge
                      |make\s+a\s+charge|tokenize|configure\s+webhook)
    | how\s+to\s+(refund|set\s+up|setup|tokenize|configure|create\s+a\s+charge)
    | what\s+currencies           # "what currencies do you support"
    | supported\s+currencies
    | webhook(s)?                 # "how do I set up webhooks"
    | tokeniz                     # "tokenization", "tokenize a card"
    | rate\s+limit                # "what are the rate limits"
    | idempotency                 # "idempotency key"
    | api\s+key                   # "invalid api key"
    | (what\s+does|what\s+is)\s+.{0,30}\s+mean  # "what does X mean"
    | how\s+do\s+i\s+(refund|charge|charge\s+a\s+card)
    | refund\s+(a\s+)?(payment|charge|transaction)(?!\s+of\s+mine)
                                  # "how to refund a payment" (not "refund transaction of mine")
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TRANSACTION_PATTERNS = re.compile(
    r"""
    (show|list|get|display|give\s+me)\s+(me\s+)?(my\s+)?
        (recent\s+|last\s+\d+\s+)?(transactions?|payments?|charges?|orders?)
    | how\s+many\s+(transactions?|payments?|charges?|failed|successful)
    | total\s+(revenue|amount|sales|charges?|payments?)
    | (last|past|this|today|yesterday)\s*(week|month|day|hour|\d+\s*days?)
    | last\s+\d+\s+(transactions?|payments?|charges?)
    | (failed|successful|pending)\s+(transactions?|payments?|charges?)
    | why\s+did\s+my\s+(payment|charge|transaction)\s+fail
    | my\s+(highest|largest|recent|last)\s+(transactions?|payments?|charges?)
    | what\s+is\s+my\s+(total|revenue|balance)
    | (revenue|earnings?|sales)\s+(today|this\s+week|this\s+month)
    | payment\s+fail(ed|ure)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _pre_classify(question: str) -> tuple[str, float] | None:
    """
    Fast rule-based classifier.  Returns (intent, confidence) if a clear
    signal is found, or None to fall through to the LLM.
    """
    if _API_DOCS_PATTERNS.search(question):
        return "api_docs", 0.97
    if _TRANSACTION_PATTERNS.search(question):
        return "transaction", 0.95
    return None


_CLASSIFY_PROMPT = """\
You are an intent classifier for an Omise payment-gateway merchant support system.

KEY DISTINCTION:
- "transaction" = the merchant is asking about their OWN transaction history, records,
  counts, amounts, or specific payments stored in the database.
  Examples: "Show my failed transactions", "How many payments did I have this week?",
            "What is my total revenue today?", "Why did my payment fail yesterday?"

- "api_docs" = the merchant is asking what an error code MEANS, how the Omise API works,
  how to integrate, or what to DO about an error.
  Examples: "What does error 402 mean?", "How do I process a refund?",
            "What currencies does Omise support?", "How do I set up webhooks?"

- "ambiguous" = the question cannot clearly be placed in either category.
  Examples: "What's wrong with my account?", "Why is my dashboard showing errors?"

Classify the merchant's question below into exactly one intent.
Return ONLY valid JSON: {{"intent": "<transaction|api_docs|ambiguous>", "confidence": <0.0-1.0>}}

Merchant question: {question}
"""


def classify_intent(state: AgentState) -> AgentState:
    """Classify the question using rule-based pre-check first, then LLM fallback."""
    question = state.get("user_question", "")
    if not question:
        return {**state, "intent": "ambiguous", "confidence": 0.0}

    # Fast path: rule-based classifier catches clear-cut cases reliably
    pre_result = _pre_classify(question)
    if pre_result is not None:
        intent, confidence = pre_result
        print(f"[classify_intent] Rule-based → intent={intent}, confidence={confidence}")
        return {**state, "intent": intent, "confidence": confidence}

    # Slow path: ask the LLM for genuinely ambiguous questions
    llm = _get_llm()
    prompt = _CLASSIFY_PROMPT.format(question=question)
    try:
        response = llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            intent = data.get("intent", "ambiguous").lower()
            confidence = float(data.get("confidence", 0.5))
        else:
            intent, confidence = "ambiguous", 0.5
    except Exception:
        intent, confidence = "ambiguous", 0.5

    if intent not in ("transaction", "api_docs", "ambiguous"):
        intent = "ambiguous"
    confidence = max(0.0, min(1.0, confidence))

    print(f"[classify_intent] LLM → intent={intent}, confidence={confidence}")
    return {**state, "intent": intent, "confidence": confidence}


# ---------------------------------------------------------------------------
# Node 3 – extract_sql_params
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
You are a data extraction assistant for an Omise payment-gateway support system.

Extract structured query parameters from the merchant's question.
Return ONLY valid JSON with these optional fields (omit fields that are not mentioned):
{{
  "date_filter": "<today|yesterday|last_7_days|last_30_days|this_month|last_month|YYYY-MM-DD or null>",
  "status": "<successful|failed|pending or null>",
  "error_code": "<401|402|422|500 or null>",
  "limit": <integer 1-100 or null>
}}

If nothing is specified for a field, use null.

Merchant question: {question}
"""


def extract_sql_params(state: AgentState) -> AgentState:
    """Use the LLM to extract structured JSON params — never raw SQL."""
    question = state.get("user_question", "")
    llm = _get_llm()
    prompt = _EXTRACT_PROMPT.format(question=question)
    try:
        response = llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
        if json_match:
            params = json.loads(json_match.group())
            # Strip null values
            params = {k: v for k, v in params.items() if v is not None}
        else:
            params = {}
    except Exception:
        params = {}

    return {**state, "sql_params": params}


# ---------------------------------------------------------------------------
# Node 4 – query_database
# ---------------------------------------------------------------------------


def query_database(state: AgentState) -> AgentState:
    """Execute the safe, merchant-scoped SQL query and store results."""
    merchant_id = state.get("merchant_id", "")
    sql_params = state.get("sql_params", {})

    try:
        rows = _query_db(merchant_id, sql_params)
        sql_str, _ = build_query(merchant_id, sql_params)
    except Exception as exc:
        return {**state, "db_results": [], "sql_query": "", "error": str(exc)}

    return {**state, "db_results": rows, "sql_query": sql_str}


# ---------------------------------------------------------------------------
# Node 5 – search_docs
# ---------------------------------------------------------------------------


def search_docs(state: AgentState) -> AgentState:
    """Vector-search the Omise API doc knowledge base."""
    question = state.get("user_question", "")
    try:
        docs = _search_docs(question, top_k=3)
    except Exception as exc:
        return {**state, "retrieved_docs": [], "error": str(exc)}

    return {**state, "retrieved_docs": docs}


# ---------------------------------------------------------------------------
# Node 6 – generate_response
# ---------------------------------------------------------------------------

_GENERATE_PROMPT = """\
You are a helpful Omise payment-gateway merchant support assistant.
Answer the merchant's question using ONLY the context provided below.
Be concise, professional, and accurate. Do NOT mention internal system details.

Merchant question: {question}

{db_section}

{docs_section}

Provide a clear, helpful answer:
"""


def generate_response(state: AgentState) -> AgentState:
    """Compose the final natural-language answer from available context."""
    question = state.get("user_question", "")
    db_results = state.get("db_results", [])
    retrieved_docs = state.get("retrieved_docs", [])

    db_section = ""
    if db_results:
        db_section = "Transaction data from the database:\n"
        for row in db_results[:20]:
            db_section += f"  - {row}\n"

    docs_section = ""
    if retrieved_docs:
        docs_section = "Relevant Omise API documentation:\n"
        for doc in retrieved_docs:
            docs_section += f"  [{doc['title']}]: {doc['content'][:400]}\n\n"

    if not db_section and not docs_section:
        return {
            **state,
            "response": (
                "I don't have enough information to answer that question. "
                "Please try rephrasing or contact Omise support at support@omise.co."
            ),
        }

    llm = _get_llm()
    prompt = _GENERATE_PROMPT.format(
        question=question,
        db_section=db_section,
        docs_section=docs_section,
    )
    try:
        response = llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        answer = f"I encountered an error while generating a response: {exc}"

    return {**state, "response": answer.strip()}


# ---------------------------------------------------------------------------
# Node 7 – filter_output
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS = [
    # API keys
    r"(sk|pk)_(live|test)_[A-Za-z0-9]{20,}",
    # Card numbers (basic Luhn-range patterns)
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
    # CVV
    r"\bcvv\s*[:\-]?\s*\d{3,4}\b",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)


def filter_output(state: AgentState) -> AgentState:
    """Redact any accidentally leaked sensitive data from the final response."""
    response = state.get("response", "")
    cleaned = _SENSITIVE_RE.sub("[REDACTED]", response)
    return {**state, "response": cleaned}
