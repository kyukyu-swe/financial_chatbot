"""
LangGraph StateGraph wiring all agent nodes with conditional routing.

Graph topology
--------------
sanitize_input
    → classify_intent
        → [route_intent]
            "transaction" → extract_sql_params → query_database → generate_response
            "api_docs"    → search_docs                         → generate_response
            "ambiguous"   → extract_sql_params → query_database ─┐
                                               → search_docs    ─┴→ generate_response
    → filter_output → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.nodes import (
    classify_intent,
    extract_sql_params,
    filter_output,
    generate_response,
    query_database,
    sanitize_input,
    search_docs,
)
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def route_intent(state: AgentState) -> str:
    """
    Decide which branch to take after intent classification.

    Returns one of the node names to route to next.
    For 'ambiguous', the graph uses a fan-out pattern via parallel nodes.
    """
    intent = state.get("intent", "ambiguous")
    if intent == "transaction":
        return "extract_sql_params"
    if intent == "api_docs":
        return "search_docs"
    # ambiguous: run both — start with extract_sql_params; search_docs is
    # added as a second entry point in the fan-out below
    return "extract_sql_params"


def route_after_sql_params(state: AgentState) -> str:
    """After extracting SQL params, always proceed to query_database."""
    return "query_database"


def route_after_query(state: AgentState) -> str:
    """
    After querying the DB, check whether we also need to search docs
    (for the ambiguous path) or go straight to generate_response.
    """
    intent = state.get("intent", "ambiguous")
    if intent == "ambiguous":
        return "search_docs"
    return "generate_response"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("sanitize_input", sanitize_input)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("extract_sql_params", extract_sql_params)
    graph.add_node("query_database", query_database)
    graph.add_node("search_docs", search_docs)
    graph.add_node("generate_response", generate_response)
    graph.add_node("filter_output", filter_output)

    # Entry point
    graph.set_entry_point("sanitize_input")

    # Linear: sanitize → classify
    graph.add_edge("sanitize_input", "classify_intent")

    # Conditional branch after classification
    graph.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "extract_sql_params": "extract_sql_params",
            "search_docs": "search_docs",
        },
    )

    # Transaction / ambiguous path
    graph.add_edge("extract_sql_params", "query_database")

    graph.add_conditional_edges(
        "query_database",
        route_after_query,
        {
            "search_docs": "search_docs",
            "generate_response": "generate_response",
        },
    )

    # api_docs / ambiguous (after DB) path
    graph.add_edge("search_docs", "generate_response")

    # Final linear edges
    graph.add_edge("generate_response", "filter_output")
    graph.add_edge("filter_output", END)

    return graph


# Compiled graph — import this in backend and elsewhere
compiled_graph = build_graph().compile()


def run_agent(question: str, merchant_id: str) -> AgentState:
    """
    Convenience function: run the full agent pipeline and return the final state.
    """
    initial_state: AgentState = {
        "user_question": question,
        "merchant_id": merchant_id,
        "intent": "",
        "confidence": 0.0,
        "sql_params": {},
        "db_results": [],
        "retrieved_docs": [],
        "sql_query": "",
        "response": "",
        "error": "",
    }
    final_state = compiled_graph.invoke(initial_state)
    return final_state
