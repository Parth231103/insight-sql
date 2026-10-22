import re
from typing import Tuple

DISALLOWED_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "EXEC", "EXECUTE", "CREATE", "REPLACE", "GRANT", "REVOKE",
    "ATTACH", "DETACH", "PRAGMA"
]


class SQLSecurityViolation(Exception):
    """Raised when a generated SQL query contains potentially destructive operations."""
    pass


def validate_and_sanitize_sql(sql: str, max_limit: int = 100) -> str:
    """Strict Read-Only SQL Guardrail:
    1. Extracts SQL block from markdown fences if present.
    2. Enforces single SELECT / WITH statements only.
    3. Blocks destructive keywords (DROP, DELETE, UPDATE, etc.).
    4. Guarantees safe upper bounds on result set size with an automatic LIMIT.
    """
    cleaned = sql.strip()
    
    # Extract from markdown block if present
    code_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if code_match:
        cleaned = code_match.group(1).strip()
    else:
        # Strip simple leading/trailing backticks if any
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    # If the LLM put introductory commentary before the SELECT/WITH, slice from SELECT/WITH
    match_start = re.search(r"\b(SELECT|WITH)\b", cleaned, flags=re.IGNORECASE)
    if match_start:
        cleaned = cleaned[match_start.start():].strip()

    # Strip trailing semicolons
    cleaned = cleaned.rstrip(";").strip()

    # Prevent multiple semicolons / command chaining
    if ";" in cleaned:
        raise SQLSecurityViolation("Multiple SQL statements and semicolon chaining are strictly prohibited.")

    # Check that query starts with SELECT or WITH
    upper_query = cleaned.upper()
    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        raise SQLSecurityViolation("Only read-only SELECT or WITH (CTE) queries are permitted.")

    # Check for forbidden mutation keywords as whole words
    for kw in DISALLOWED_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", upper_query):
            raise SQLSecurityViolation(f"Destructive operation detected: '{kw}' keyword is forbidden in read-only mode.")

    # Append LIMIT if not present
    if not re.search(r"\bLIMIT\s+\d+\b", upper_query):
        cleaned += f" LIMIT {max_limit}"

    return cleaned


if __name__ == "__main__":
    # Test valid queries
    q1 = "SELECT full_name, city FROM customers WHERE city = 'Pune'"
    print("Valid query:", validate_and_sanitize_sql(q1))

    # Test blocked queries
    try:
        validate_and_sanitize_sql("DROP TABLE customers")
    except SQLSecurityViolation as e:
        print("Blocked correctly:", e)
