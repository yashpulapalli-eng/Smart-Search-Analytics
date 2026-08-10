"""
load_to_sqlite.py
Loads all generated CSVs (products, users, sessions, search/click/cart/purchase
events, experiment assignments) into a single SQLite database for SQL analysis.

Output: data/processed/shopsense.db
"""

import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROCESSED_DIR / "shopsense.db"

TABLES = {
    "products": RAW_DIR / "products.csv",
    "sessions": PROCESSED_DIR / "sessions.csv",
    "search_events": PROCESSED_DIR / "search_events.csv",
    "click_events": PROCESSED_DIR / "click_events.csv",
    "cart_events": PROCESSED_DIR / "cart_events.csv",
    "purchase_events": PROCESSED_DIR / "purchase_events.csv",
    "experiment_assignments": PROCESSED_DIR / "experiment_assignments.csv",
}


def load_all():
    conn = sqlite3.connect(DB_PATH)

    for table_name, csv_path in TABLES.items():
        if not csv_path.exists():
            print(f"WARNING: {csv_path} not found, skipping '{table_name}'")
            continue
        df = pd.read_csv(csv_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"Loaded '{table_name}': {len(df)} rows")

    # Helpful indexes for join/filter performance
    cur = conn.cursor()
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_search_user ON search_events(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_search_session ON search_events(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_click_search ON click_events(search_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_cart_search ON cart_events(search_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_search ON purchase_events(search_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_assignments_user ON experiment_assignments(user_id)",
    ]
    for stmt in index_statements:
        cur.execute(stmt)
    conn.commit()

    print(f"\nDatabase ready -> {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    load_all()
