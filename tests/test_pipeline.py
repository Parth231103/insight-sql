import sys
import sqlite3
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from graph import app_graph, self_heal_node, execute_sql_node, AgentState
from db import get_schema_summary
from config import DB_PATH
from security import validate_and_sanitize_sql, SQLSecurityViolation


def test_schema_summary():
    conn = sqlite3.connect(DB_PATH)
    schema = get_schema_summary(conn)
    conn.close()
    assert "Table: customers" in schema
    assert "Table: orders" in schema
    assert "Table: order_items" in schema


def test_sql_guardrail_blocks_destructive_commands():
    with pytest.raises(SQLSecurityViolation):
        validate_and_sanitize_sql("DROP TABLE customers;")

    with pytest.raises(SQLSecurityViolation):
        validate_and_sanitize_sql("DELETE FROM orders WHERE order_id = 1;")

    with pytest.raises(SQLSecurityViolation):
        validate_and_sanitize_sql("UPDATE products SET unit_price = 0;")


def test_sql_guardrail_allows_select_and_cte():
    q1 = validate_and_sanitize_sql("SELECT full_name, city FROM customers")
    assert q1.startswith("SELECT full_name, city FROM customers")
    assert "LIMIT" in q1

    q2 = validate_and_sanitize_sql("WITH cte AS (SELECT * FROM orders) SELECT * FROM cte")
    assert q2.startswith("WITH cte")


def test_self_healing_node_recovers_missing_column():
    conn = sqlite3.connect(DB_PATH)
    schema = get_schema_summary(conn)
    conn.close()

    broken_state: AgentState = {
        "question": "What is the average order value per customer city?",
        "schema_info": schema,
        "sql_query": "SELECT c.city, AVG(o.total_price) FROM customers c JOIN orders o ON c.user_id = o.user_id GROUP BY c.city",
        "query_result": [],
        "column_names": [],
        "error_message": "Database Execution Error: no such column: c.user_id",
        "iteration": 0,
        "reflection_notes": "",
        "executive_summary": "",
        "chart_config": {},
        "was_self_healed": False
    }

    healed = self_heal_node(broken_state)
    assert healed["was_self_healed"] is True
    assert healed["sql_query"] is not None
