import sqlite3
from datetime import date

from flask import Blueprint, jsonify, request, session

import clock
from calendar_db import load_nonworking
from db import get_db
from decorators import librarian_required
from loans import get_due_date
from routes.helpers import json_body, pick

nonworking_bp = Blueprint("nonworking", __name__, url_prefix="/api")

REASONS = ("Holiday", "School suspension", "Other")


def _parse_date(value):
    """A date from exactly 'YYYY-MM-DD', or None for anything else."""
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None   # rejects forms like 2026-W45-1


@nonworking_bp.get("/nonworking")
def list_nonworking():
    """Every marked day. Any logged-in user can read it (the pages use it to preview due dates)."""
    if "user_id" not in session:
        return jsonify(ok=False, error="Login required"), 401

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT NonWorkingDate, Reason, LibrarianID FROM NonWorkingDay ORDER BY NonWorkingDate"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@nonworking_bp.post("/librarian/nonworking")
@librarian_required
def add_nonworking():
    """Mark a day as non-working. Body: {"date": "2026-11-10", "reason": "Holiday"}.
    Only today or a future day, and never a Sunday (Sundays are skipped by the code already)."""
    body = json_body()
    day = _parse_date(pick(body, "date", "NonWorkingDate"))
    if day is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-10"), 400

    reason = pick(body, "reason", "Reason")
    if reason not in REASONS:
        return jsonify(ok=False, error="reason must be Holiday, School suspension or Other"), 400

    if day < clock.now().date():
        return jsonify(ok=False, error="Only today or a future date can be marked"), 400
    if day.weekday() == 6:
        return jsonify(ok=False, error="Sundays are already skipped"), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO NonWorkingDay (NonWorkingDate, Reason, LibrarianID) VALUES (?, ?, ?)",
            (day.isoformat(), reason, session["user_id"]),
        )
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "NonWorkingDay.NonWorkingDate" in str(error):
            return jsonify(ok=False, error="That day is already marked"), 409
        raise
    finally:
        conn.close()
    return jsonify(ok=True, date=day.isoformat(), reason=reason), 201


@nonworking_bp.delete("/librarian/nonworking/<day>")
@librarian_required
def remove_nonworking(day):
    """Make a marked day a working day again. Past days stay as they are, because
    loans and fines were already counted with them."""
    parsed = _parse_date(day)
    if parsed is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-10"), 400
    if parsed < clock.now().date():
        return jsonify(ok=False, error="A past date can't be changed"), 400

    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM NonWorkingDay WHERE NonWorkingDate = ?", (parsed.isoformat(),))
        if cursor.rowcount != 1:
            return jsonify(ok=False, error="That day is not marked"), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, date=parsed.isoformat())


@nonworking_bp.get("/librarian/nonworking/impact")
@librarian_required
def nonworking_impact():
    """How many borrowed books get a different due date if this day is switched
    (marked if it is a working day, unmarked if it is already marked). ?date=2026-11-10"""
    day = _parse_date(request.args.get("date", "").strip())
    if day is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-10"), 400

    conn = get_db()
    try:
        current = load_nonworking(conn)
        switched = current ^ {day}          # add the day if missing, remove it if present
        borrow_ids = [r["BorrowID"] for r in conn.execute("SELECT BorrowID FROM Borrow WHERE Status = 'Borrowed'")]
        affected = sum(
            1 for borrow_id in borrow_ids
            if get_due_date(conn, borrow_id, current) != get_due_date(conn, borrow_id, switched)
        )
    finally:
        conn.close()
    return jsonify(ok=True, borrowed_affected=affected)
