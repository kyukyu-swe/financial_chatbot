"""
Streamlit chat dashboard for the Omise merchant support chatbot.

Features
--------
- Sidebar merchant selector (mch_001 – mch_005)
- st.chat_message style conversation history
- Intent badge + confidence score on each reply
- Expandable "SQL Query" panel (shown for transaction/ambiguous intents)
- Expandable "API Docs Retrieved" panel (shown for api_docs/ambiguous intents)
- Expandable "Raw DB Results" panel
"""

from __future__ import annotations

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
DEFAULT_MERCHANT = os.getenv("SESSION_MERCHANT_ID", "mch_001")

MERCHANTS = ["mch_001", "mch_002", "mch_003", "mch_004", "mch_005"]

INTENT_COLORS = {
    "transaction": "#1a73e8",
    "api_docs": "#0f9d58",
    "ambiguous": "#f4b400",
}

INTENT_LABELS = {
    "transaction": "📊 Transaction Data",
    "api_docs": "📖 API Docs",
    "ambiguous": "🔀 Ambiguous",
}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Omise Merchant Support",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
        .intent-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            color: white;
            font-size: 0.78rem;
            font-weight: 600;
            margin-right: 8px;
        }
        .confidence-bar-bg {
            background: #e8eaed;
            border-radius: 4px;
            height: 6px;
            width: 160px;
            display: inline-block;
            vertical-align: middle;
            margin-left: 4px;
        }
        .confidence-bar-fill {
            background: #1a73e8;
            border-radius: 4px;
            height: 6px;
        }
        .meta-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }
        .confidence-label {
            font-size: 0.75rem;
            color: #5f6368;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helper: render an assistant message with metadata panels
# ---------------------------------------------------------------------------


def render_assistant_message(msg: dict) -> None:
    intent = msg.get("intent", "")
    confidence = msg.get("confidence", 0.0)
    color = INTENT_COLORS.get(intent, "#9aa0a6")
    label = INTENT_LABELS.get(intent, intent or "Unknown")
    confidence_pct = int(confidence * 100)
    bar_width = max(2, confidence_pct)

    st.markdown(
        f"""
        <div class="meta-row">
            <span class="intent-badge" style="background:{color};">{label}</span>
            <span class="confidence-label">Confidence: {confidence_pct}%</span>
            <div class="confidence-bar-bg">
                <div class="confidence-bar-fill" style="width:{bar_width}%;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(msg["content"])

    if msg.get("error"):
        st.warning(f"⚠️ {msg['error']}")

    if msg.get("sql_query") and intent in ("transaction", "ambiguous"):
        with st.expander("🗄️ SQL Query executed"):
            st.code(msg["sql_query"], language="sql")

    if msg.get("db_results") and intent in ("transaction", "ambiguous"):
        with st.expander(f"📋 Raw DB results ({len(msg['db_results'])} rows)"):
            st.dataframe(msg["db_results"], use_container_width=True)

    if msg.get("retrieved_docs") and intent in ("api_docs", "ambiguous"):
        with st.expander(f"📚 API Docs retrieved ({len(msg['retrieved_docs'])} chunks)"):
            for doc in msg["retrieved_docs"]:
                st.markdown(f"**{doc.get('title', 'Doc')}** — *{doc.get('topic', '')}*")
                st.caption(f"Distance: {doc.get('distance', '')}")
                st.markdown(doc.get("content", ""))
                st.divider()


# ---------------------------------------------------------------------------
# Input handler
# ---------------------------------------------------------------------------


def send_question(question: str, merchant_id: str) -> None:
    """Append user message, call API, append assistant reply, then rerun."""
    if not question.strip():
        return

    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("Thinking…"):
        try:
            resp = requests.post(
                f"{API_BASE}/chat",
                json={"question": question, "merchant_id": merchant_id},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            data = {
                "response": "❌ Could not reach the backend API. Is it running at `" + API_BASE + "`?",
                "intent": "",
                "confidence": 0.0,
                "db_results": [],
                "retrieved_docs": [],
                "sql_query": "",
                "error": "Connection refused",
            }
        except Exception as exc:
            data = {
                "response": f"❌ Request failed: {exc}",
                "intent": "",
                "confidence": 0.0,
                "db_results": [],
                "retrieved_docs": [],
                "sql_query": "",
                "error": str(exc),
            }

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": data.get("response", ""),
            "intent": data.get("intent", ""),
            "confidence": data.get("confidence", 0.0),
            "db_results": data.get("db_results", []),
            "retrieved_docs": data.get("retrieved_docs", []),
            "sql_query": data.get("sql_query", ""),
            "error": data.get("error", ""),
        }
    )
    st.rerun()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image(
        "https://www.omise.co/assets/images/omise-logo.svg",
        width=140,
    )
    st.markdown("## Merchant Support Chat")
    st.divider()

    merchant_id: str = st.selectbox(
        "Select Merchant",
        options=MERCHANTS,
        index=MERCHANTS.index(DEFAULT_MERCHANT) if DEFAULT_MERCHANT in MERCHANTS else 0,
        help="Switch between merchant accounts to see their data.",
    )

    st.divider()
    st.markdown("### Quick Prompts")
    quick_prompts = [
        "Show my last 10 transactions",
        "How many failed transactions did I have this month?",
        "What does error 402 mean?",
        "How do I set up webhooks?",
        "Show failed transactions in the last 7 days",
        "How do I tokenize a card?",
        "What currencies are supported?",
    ]
    selected_quick: str | None = None
    for prompt in quick_prompts:
        if st.button(prompt, use_container_width=True, key=f"qp_{prompt}"):
            selected_quick = prompt

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown(
        "<p style='font-size:0.72rem;color:#9aa0a6;'>API: "
        f"<code>{API_BASE}</code></p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("💳 Omise Merchant Support")
st.caption(f"Logged in as **{merchant_id}**  ·  Powered by LangGraph + LLM")

# Replay conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_assistant_message(msg)
        else:
            st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

# Quick prompt buttons take priority
if selected_quick:
    send_question(selected_quick, merchant_id)

# Regular chat input
if user_input := st.chat_input("Ask about your transactions or the Omise API…"):
    send_question(user_input, merchant_id)
