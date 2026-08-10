"""
run_analytics.py
Executes each labeled query block in analytics_queries.sql against
shopsense.db and prints the results in a readable format.
"""

import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "shopsense.db"
SQL_PATH = PROJECT_ROOT / "src" / "sql" / "analytics_queries.sql"

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 150)


def split_queries(sql_text):
    """Split the .sql file into (label, query) pairs using the '-- N. LABEL' comments."""
    blocks = []
    current_label = None
    current_lines = []

    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- ") and any(stripped[3:].startswith(f"{i}.") for i in range(1, 20)):
            if current_label and current_lines:
                blocks.append((current_label, "\n".join(current_lines)))
            current_label = stripped[3:]
            current_lines = []
        elif current_label:
            current_lines.append(line)

    if current_label and current_lines:
        blocks.append((current_label, "\n".join(current_lines)))

    return blocks


def run_all():
    conn = sqlite3.connect(DB_PATH)
    sql_text = SQL_PATH.read_text()
    queries = split_queries(sql_text)

    for label, query in queries:
        query = query.strip()
        if not query:
            continue
        print("\n" + "=" * 90)
        print(label)
        print("=" * 90)
        try:
            df = pd.read_sql_query(query, conn)
            print(df.to_string(index=False))
        except Exception as e:
            print(f"ERROR running this query: {e}")

    conn.close()


if __name__ == "__main__":
    run_all()
