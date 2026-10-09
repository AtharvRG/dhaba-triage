"""
Idempotency store: same ticket ID twice -> same stored answer.
SQLite, stdlib only. The money gate never runs twice for one ticket.
"""
import sqlite3
import threading

from app.schemas import TriageResponse

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def init(db_path: str = "dhaba.db") -> None:
    global _conn
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS triage_results (
               ticket_id TEXT PRIMARY KEY,
               response  TEXT NOT NULL,
               created_at TEXT DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    _conn.commit()


def get(ticket_id: str) -> TriageResponse | None:
    with _lock:
        row = _conn.execute(
            "SELECT response FROM triage_results WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    if row is None:
        return None
    resp = TriageResponse.model_validate_json(row[0])
    resp.replayed = True      # proof, right in the payload
    return resp


def put(ticket_id: str, response: TriageResponse) -> None:
    with _lock:
        _conn.execute(
            """INSERT INTO triage_results (ticket_id, response)
               VALUES (?, ?)
               ON CONFLICT(ticket_id) DO NOTHING""",
            (ticket_id, response.model_dump_json()),
        )
        _conn.commit()