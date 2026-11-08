import sqlite3
from datetime import date

from flask import Blueprint, jsonify, request, session

import clock
from calendar_db import load_nonworking
from db import get_db
from decorators import librarian_required, login_required
from loans import get_due_date
from routes.helpers import json_body, pick

nonworking_bp = Blueprint("nonworking", __name__, url_prefix="/api")

REASONS = ("Holiday", "School suspension", "Other")


def _parse_date(value):
    """A date from 'YYYY-MM-DD', or None for anything else."""
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def borrowed_affected(conn, day: date, nonworking: set[date]) -> int:
    """How many books out right now would get a different due date if `day` were toggled.

    A marked day is simulated as removed, an unmarked day as added. Each Borrowed loan's
    due date is worked out both ways with get_due_date, so the answer follows the real rules
    (Sundays, renewals, other marked days) instead of a separate formula.
    """
    toggled = (nonworking - {day}) if day in nonworking else (nonworking | {day})
    ids = [r["BorrowID"] for r in conn.execute("SELECT BorrowID FROM Borrow WHERE Status = 'Borrowed'").fetchall()]
    return sum(
        1 for borrow_id in ids
        if get_due_date(conn, borrow_id, nonworking) != get_due_date(conn, borrow_id, toggled)
    )


@nonworking_bp.get("/nonworking")
@login_required
def list_nonworking():
    """Every marked day. Students need it too, to preview due dates."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT NonWorkingDate, Reason, LibrarianID FROM NonWorkingDay ORDER BY NonWorkingDate"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@nonworking_bp.get("/librarian/nonworking/impact")
@librarian_required
def nonworking_impact():
    """The warning in the side panel: how many borrowed books' due dates would move."""
    day = _parse_date(request.args.get("date", ""))
    if day is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-03"), 400

    conn = get_db()
    try:
        count = borrowed_affected(conn, day, load_nonworking(conn))
    finally:
        conn.close()
    return jsonify(borrowed_affected=count)


@nonworking_bp.post("/librarian/nonworking")
@librarian_required
def add_nonworking():
    """Mark a day. Body: {"date": "2026-12-25", "reason": "Holiday"}."""
    body = json_body()
    day = _parse_date(pick(body, "date", "NonWorkingDate"))
    reason = pick(body, "reason", "Reason")

    if day is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-03"), 400
    if reason not in REASONS:
        return jsonify(ok=False, error="reason must be Holiday, School suspension or Other"), 400
    if day < clock.now().date():
        return jsonify(ok=False, error="Only today or future dates can be marked"), 400
    if day.weekday() == 6:
        return jsonify(ok=False, error="Sundays are always skipped, so they can't be marked"), 400

    conn = get_db()
    try:
        affected = borrowed_affected(conn, day, load_nonworking(conn))
        try:
            conn.execute(
                "INSERT INTO NonWorkingDay (NonWorkingDate, Reason, LibrarianID) VALUES (?, ?, ?)",
                (day.isoformat(), reason, session["user_id"]),
            )
            conn.commit()
        except sqlite3.IntegrityError as error:
            conn.rollback()
            if "NonWorkingDay.NonWorkingDate" in str(error):
                return jsonify(ok=False, error="That date is already marked"), 409
            raise
    finally:
        conn.close()
    return jsonify(ok=True, date=day.isoformat(), reason=reason, borrowed_affected=affected), 201


@nonworking_bp.delete("/librarian/nonworking/<day_text>")
@librarian_required
def remove_nonworking(day_text):
    """Unmark a day.

    Only today or a future day can be unmarked. A past day already decided overdue
    checks and saved fines, so changing it would rewrite history.
    """
    day = _parse_date(day_text)
    if day is None:
        return jsonify(ok=False, error="date must be a date like 2026-11-03"), 400
    if day < clock.now().date():
        return jsonify(ok=False, error="Past dates can't be unmarked"), 400

    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM NonWorkingDay WHERE NonWorkingDate = ?", (day.isoformat(),))
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify(ok=False, error="That date is not marked"), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, date=day.isoformat())
