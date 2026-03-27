"""
Railway startup script.
Runs ingest.py only if the database does not yet exist.
This prevents re-ingestion on every dyno restart.
"""
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "o2c.db")

if not os.path.exists(DB_PATH):
    print("Database not found — running ingestion...")
    import ingest
    ingest.main()
    print("Ingestion complete.")
else:
    print(f"Database found at {DB_PATH} — skipping ingestion.")
