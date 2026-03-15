# Omise Merchant Support Chatbot

A demo AI chatbot where merchants can ask questions about their transaction history and Omise API documentation in natural language. A **Router Agent** (built with LangGraph) classifies the intent of each question and routes it to the correct data source — a live SQLite database or a local ChromaDB vector store.

---

## Architecture

```
Merchant (Streamlit)
        │
        ▼
  FastAPI /chat  ──── rate limit: 10 req/min per merchant
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                  LangGraph Agent                    │
│                                                     │
│  sanitize_input                                     │
│       │                                             │
│  classify_intent  ◄── rule-based pre-classifier     │
│       │                + LLM fallback               │
│       ├─── "transaction" ──► extract_sql_params     │
│       │                           │                 │
│       │                      query_database         │
│       │                      (SQLite, read-only)    │
│       │                                             │
│       ├─── "api_docs" ──────► search_docs           │
│       │                      (ChromaDB + embeddings)│
│       │                                             │
│       └─── "ambiguous" ─────► both paths above     │
│                                     │               │
│                              generate_response      │
│                              (LLM explains results) │
│                                     │               │
│                              filter_output          │
│                          (redact sensitive data)    │
└─────────────────────────────────────────────────────┘
```

### Intent Classification — Two-Layer Design

Questions are classified by a **rule-based pre-classifier first**, with the LLM only called for genuinely ambiguous questions. This prevents small local models (e.g. `gemma3:1b`) from misrouting clear-cut questions.

| Layer | Method | Example |
|---|---|---|
| 1 | Regex rules | `"What does error 402 mean?"` → `api_docs` |
| 2 | LLM (fallback) | `"What's wrong with my account?"` → LLM decides |

---

## Project Structure

```
omise-chatbot/
├── agent/
│   ├── graph.py          # LangGraph StateGraph — nodes + conditional routing
│   ├── nodes.py          # All 7 node functions
│   └── state.py          # AgentState TypedDict
├── backend/
│   ├── main.py           # FastAPI app (POST /chat, GET /health)
│   └── schemas.py        # Pydantic request/response models
├── db/
│   ├── database.py       # SQLAlchemy model (transactions table)
│   ├── seed.py           # Seeds 200 transactions (random_state=42)
│   └── transactions.db   # SQLite database (auto-created on first run)
├── docs/
│   └── fake_docs.py      # 12 Omise API documentation entries
├── frontend/
│   └── dashboard.py      # Streamlit chat UI
├── ml/
│   └── embeddings.py     # Local sentence-transformers embeddings
├── security/
│   ├── sanitizer.py      # Input sanitizer — blocks prompt injection
│   └── validator.py      # SQL validator — SELECT-only, blocks dangerous keywords
├── tools/
│   ├── db_tool.py        # Read-only SQLite query executor
│   └── docs_tool.py      # ChromaDB similarity search
├── vector_store/
│   └── setup.py          # ChromaDB setup + doc ingestion (idempotent)
├── chroma_db/            # Persisted ChromaDB collection (auto-created)
├── .env                  # Your local config (not committed)
├── .env.example          # Config template
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | [LangGraph](https://github.com/langchain-ai/langgraph) StateGraph |
| LLM (local) | [Ollama](https://ollama.com) + `gemma3:1b` |
| LLM (cloud) | OpenAI `gpt-4o-mini` |
| Vector DB | [ChromaDB](https://www.trychroma.com) (local, no API key) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, free) |
| Database | SQLite + SQLAlchemy |
| Backend | FastAPI + slowapi (rate limiting) |
| Frontend | Streamlit |
| Validation | Pydantic v2 |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running (for local LLM mode)

### 1. Clone and install dependencies

```bash
cd omise-chatbot
pip install -r requirements.txt
```

### 2. Pull the Ollama model

```bash
ollama pull gemma3:1b
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box with Ollama
```

### 4. Start the backend

```bash
# On first run: seeds the SQLite DB and ingests docs into ChromaDB automatically
python -m backend.main
```

The API will be available at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

### 5. Start the frontend (separate terminal)

```bash
python -m streamlit run frontend/dashboard.py
```

Open `http://localhost:8501` in your browser.

> **Windows / Git Bash note:** Use `python -m streamlit` instead of `streamlit` directly if the command is not found.

---

## Configuration

All settings are controlled via `.env`:

```env
# Switch between local Ollama and OpenAI
LLM_PROVIDER=ollama          # "ollama" or "openai"

# Ollama (local, free)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:1b

# OpenAI (cloud, requires API key)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Frontend → Backend connection
API_BASE=http://localhost:8000

# Default merchant pre-selected in the sidebar
SESSION_MERCHANT_ID=mch_001
```

To switch to OpenAI, set `LLM_PROVIDER=openai` and add your `OPENAI_API_KEY`.

---

## Demo Test Cases

### Transaction queries (routes to SQLite)
```
"Why did my payment fail yesterday?"
"How many successful payments did I have this week?"
"Show me my highest transactions this month"
"What is my total revenue today?"
"Show my last 10 transactions"
```

### API doc queries (routes to ChromaDB)
```
"What does error 402 mean?"
"How do I process a refund?"
"What currencies do you support?"
"How do I set up webhooks?"
"How do I tokenize a card?"
```

### Ambiguous queries (routes to both)
```
"What's wrong with my account?"
"Why is my dashboard showing errors?"
```

---

## Fake Database

Seeded with `random_state=42` for reproducibility:

- **5 merchants:** `mch_001` – `mch_005`
- **200 transactions** total (40 per merchant)
- **70% successful / 30% failed** split
- **Failed error codes:** 401, 402, 422, 500
- **Locations:** Bangkok, Chiang Mai, Phuket, Singapore, London
- **Amounts:** THB 100 – 50,000 (log-normal distribution)
- **Timestamps:** spread over the last 30 days

To re-seed the database from scratch:
```bash
python -m db.seed
```

---

## Security

| Layer | Description |
|---|---|
| `merchant_id` isolation | Always injected from session — never read from user input |
| SQL validator | Blocks all non-SELECT statements (DROP, INSERT, UPDATE, UNION, PRAGMA, etc.) |
| Read-only connection | SQLite opened in read-only mode |
| Input sanitizer | Strips prompt injection patterns, limits input to 500 characters |
| Output filter | Redacts API keys and card numbers from LLM responses |
| Rate limiting | 10 requests per minute per `merchant_id` |

---

## API Reference

### `POST /chat`

```json
// Request
{
  "question": "What does error 402 mean?",
  "merchant_id": "mch_001"
}

// Response
{
  "merchant_id": "mch_001",
  "question": "What does error 402 mean?",
  "intent": "api_docs",
  "confidence": 0.97,
  "response": "Error 402 Payment Required indicates the charge was declined...",
  "db_results": [],
  "retrieved_docs": [{ "title": "Error 402 – Payment Required", ... }],
  "sql_query": "",
  "error": ""
}
```

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## Frontend Features

- **Merchant selector** in the sidebar — switch between `mch_001` to `mch_005` to simulate different sessions
- **Intent badge** — color-coded label showing `Transaction Data`, `API Docs`, or `Ambiguous`
- **Confidence bar** — visual indicator of classifier confidence
- **Quick prompt buttons** — one-click example queries
- **Expandable SQL panel** — shows the exact parameterized query executed
- **Expandable DB results panel** — raw transaction rows as a dataframe
- **Expandable API docs panel** — retrieved doc chunks with similarity distance
- **Clear conversation** button

---

## Replacing ChromaDB with Pinecone (Production)

ChromaDB is used for this demo because it runs locally with no API key. To switch to Pinecone in production:

1. Replace `vector_store/setup.py` with a Pinecone client
2. Update `tools/docs_tool.py` to query Pinecone instead of ChromaDB
3. Add `PINECONE_API_KEY` and `PINECONE_INDEX` to `.env`

The rest of the agent (nodes, graph, security) requires no changes.
