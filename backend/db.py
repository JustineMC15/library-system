import sqlite3
from config import DB_PATH


def get_db():
    """Open a new connection. Call conn.close() when the request is done."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # read columns by name, e.g. row["BookTitle"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless this is on
    return conn
