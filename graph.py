import re
import sys
import sqlite3
from typing import TypedDict, List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from config import get_llm, DB_PATH
from db import get_schema_summary
from security import validate_and_sanitize_sql, SQLSecurityViolation


class AgentState(TypedDict, total=False):
    question: str
    schema_info: str
    sql_query: str
    query_result: List[Dict[str, Any]]
    column_names: List[str]
    error_message: Optional[str]
    iteration: int
    reflection_notes: str
    executive_summary: str
    chart_config: Dict[str, Any]
    was_self_healed: bool
    skip_synthesis: bool


def inspect_schema_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Inspects the database tables and columns."""
    conn = sqlite3.connect(DB_PATH)
    schema = get_schema_summary(conn)
    conn.close()
    return {"schema_info": schema, "iteration": 0, "was_self_healed": False}


def generate_sql_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Generates SQL from user question and schema."""
    llm = get_llm()
    prompt = f"""You are an elite SQL Database Engineer.
Given the SQLite database schema and business question below, write an exact, optimized SQLite SELECT query.

DATABASE SCHEMA:
{state['schema_info']}

BUSINESS QUESTION:
{state['question']}

RULES:
1. Output ONLY the raw SQL query. Do not wrap in markdown quotes, do not explain.
2. Only write read-only SELECT or WITH statements.
3. Be careful with table joins and foreign keys.
4. Ensure all column names match the schema exactly.
"""
    res = llm.invoke([SystemMessage(content=prompt)])
    raw_sql = res.content.strip()
    return {"sql_query": raw_sql, "error_message": None}


def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Validates read-only AST safety and executes the SQL query."""
    raw_sql = state["sql_query"]

    # 1. Validate security
    try:
        clean_sql = validate_and_sanitize_sql(raw_sql)
    except SQLSecurityViolation as e:
        return {"error_message": f"Security Guardrail Violation: {str(e)}", "sql_query": raw_sql}

    # 2. Execute on SQLite database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute(clean_sql)
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description] if cur.description else []
        result_dicts = [dict(r) for r in rows]
        conn.close()
        return {
            "sql_query": clean_sql,
            "query_result": result_dicts,
            "column_names": col_names,
            "error_message": None,
        }
    except Exception as e:
        conn.close()
        return {
            "sql_query": clean_sql,
            "query_result": [],
            "column_names": [],
            "error_message": f"Database Execution Error: {str(e)}",
        }


def self_heal_node(state: AgentState) -> Dict[str, Any]:
    """Node 4 (Self-Healing Reflection Loop):
    Inspects the execution error and schema constraints, autonomously diagnosing and rewriting the query.
    """
    llm = get_llm()
    current_iter = state.get("iteration", 0) + 1

    prompt = f"""You are a Database Self-Healing Agent.
The previous SQL query failed during execution. Analyze the error and fix the SQL query.

DATABASE SCHEMA:
{state['schema_info']}

ORIGINAL QUESTION:
{state['question']}

FAILED SQL QUERY:
{state['sql_query']}

DATABASE ERROR:
{state['error_message']}

INSTRUCTIONS:
1. Identify why the query failed (e.g. unknown column, syntax error, missing join).
2. Write the corrected SQL query.
3. Output format: First line: Brief 1-sentence diagnostic reflection starting with 'DIAGNOSIS:'.
   Followed by the corrected SQL query without markdown code blocks.
"""
    res = llm.invoke([HumanMessage(content=prompt)])
    text = res.content.strip()

    reflection = "Self-corrected query syntax based on schema feedback."
    fixed_sql = text
    if "DIAGNOSIS:" in text:
        parts = text.split("DIAGNOSIS:", 1)[1].split("\n", 1)
        reflection = parts[0].strip()
        fixed_sql = parts[1].strip() if len(parts) > 1 else parts[0].strip()

    return {
        "sql_query": fixed_sql,
        "iteration": current_iter,
        "reflection_notes": reflection,
        "was_self_healed": True,
    }


def should_continue(state: AgentState) -> str:
    """Conditional Edge: Determines whether to self-heal or synthesize insights."""
    if state.get("error_message") is None:
        return "synthesize"
    if state.get("iteration", 0) >= 3:
        return "synthesize"
    return "self_heal"


def synthesize_insights_node(state: AgentState) -> Dict[str, Any]:
    """Node 5: Generates executive narrative summary and visualization guidance."""
    if state.get("skip_synthesis", False):
        return {"executive_summary": "Skipped for benchmark evaluation.", "chart_config": {}}

    results = state.get("query_result", [])
    if state.get("error_message"):
        summary = f"⚠️ Could not execute query safely after {state.get('iteration', 1)} attempts: {state.get('error_message')}"
        chart_cfg = {"type": "none"}
        return {"executive_summary": summary, "chart_config": chart_cfg}

    llm = get_llm()
    sample_data = results[:10]

    prompt = f"""You are a Chief Data Officer presenting insights to executives.
Summarize the following data findings answering: "{state['question']}"

DATA RESULTS (Sample):
{sample_data}

COLUMNS:
{state.get('column_names', [])}

TASK:
1. Provide a concise 3-bullet executive summary answering the question directly with exact numbers.
2. Recommend the best visualization type: 'bar', 'line', 'pie', or 'table'.
"""
    res = llm.invoke([HumanMessage(content=prompt)])
    summary_text = res.content.strip()

    # Determine recommended chart type heuristically
    cols = state.get("column_names", [])
    chart_type = "table"
    x_col = cols[0] if cols else ""
    y_col = cols[1] if len(cols) > 1 else ""

    if len(cols) >= 2 and any("date" in c.lower() for c in cols):
        chart_type = "line"
    elif len(cols) >= 2 and any(isinstance(results[0].get(c), (int, float)) for c in cols[1:] if results):
        chart_type = "bar"

    chart_cfg = {
        "type": chart_type,
        "x": x_col,
        "y": y_col,
        "title": state["question"][:50],
    }

    return {"executive_summary": summary_text, "chart_config": chart_cfg}


def build_insight_graph():
    """Builds and compiles the self-healing LangGraph StateGraph."""
    workflow = StateGraph(AgentState)

    workflow.add_node("inspect_schema", inspect_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("self_heal", self_heal_node)
    workflow.add_node("synthesize", synthesize_insights_node)

    workflow.add_edge(START, "inspect_schema")
    workflow.add_edge("inspect_schema", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")

    workflow.add_conditional_edges(
        "execute_sql",
        should_continue,
        {
            "self_heal": "self_heal",
            "synthesize": "synthesize",
        },
    )

    workflow.add_edge("self_heal", "execute_sql")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


app_graph = build_insight_graph()


if __name__ == "__main__":
    print("Testing InsightSQL LangGraph Workflow...")
    test_question = "What are the top 3 best selling products by total revenue?"
    final_state = app_graph.invoke({"question": test_question})
    print("\n--- GENERATED SQL ---")
    print(final_state["sql_query"])
    print(f"\n--- WAS SELF HEALED: {final_state['was_self_healed']} ---")
    print(f"--- ROWS RETRIEVED: {len(final_state['query_result'])} ---")
    print("\n--- EXECUTIVE SUMMARY ---")
    print(final_state["executive_summary"])
