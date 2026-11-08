from datetime import date

from flask import Blueprint, jsonify, request

import clock
from calendar_db import load_nonworking
from db import get_db
from decorators import librarian_required
from loans import get_due_date
from working_days import days_overdue, fine

librarian_bp = Blueprint("librarian", __name__, url_prefix="/api/librarian")

REQUEST_TYPES = ("borrow", "renew", "return")
HISTORY_DEFAULT_LIMIT = 100
HISTORY_MAX_LIMIT = 500


def _student_name(row):
    """Same format as the queue: 'Last, First M.'"""
    middle = f" {row['MiddleInitial']}." if row["MiddleInitial"] else ""
    return f"{row['LastName']}, {row['FirstName']}{middle}"


def overdue_loans(conn, today: date, nonworking: set[date]) -> list[dict]:
    """Every Borrowed book that is overdue today, most overdue first.

    A book is listed by the same test as the "Unreturned books" check (days overdue
    up to today > 0). DaysLate and Fine stop at the day a return was requested, the
    same as the student's own list, so waiting for approval never adds to the fine.
    """
    rows = conn.execute(
        """
        SELECT b.BorrowID, b.StudentID, b.BookID, bk.BookTitle,
               s.LastName, s.FirstName, s.MiddleInitial,
               (SELECT rt.RequestedAt FROM "Return" AS rt
                 WHERE rt.BorrowID = b.BorrowID AND rt.Status = 'Pending') AS ReturnRequestedAt
        FROM Borrow AS b
        JOIN Book AS bk ON bk.BookID = b.BookID
        JOIN Student AS s ON s.StudentID = b.StudentID
        WHERE b.Status = 'Borrowed'
        """
    ).fetchall()

    result = []
    for r in rows:
        due = get_due_date(conn, r["BorrowID"], nonworking)
        if days_overdue(due, today, nonworking) <= 0:
            continue
        requested = r["ReturnRequestedAt"]
        fine_until = date.fromisoformat(requested[:10]) if requested else today
        late = days_overdue(due, fine_until, nonworking)
        result.append({
            "BorrowID": r["BorrowID"],
            "StudentID": r["StudentID"],
            "StudentName": _student_name(r),
            "BookID": r["BookID"],
            "BookTitle": r["BookTitle"],
            "DueDate": due.isoformat(),
            "DaysLate": late,
            "Fine": fine(late),
            "ReturnPending": requested is not None,
        })

    result.sort(key=lambda o: (-o["DaysLate"], o["DueDate"], o["BorrowID"]))
    return result


@librarian_bp.get("/stats")
@librarian_required
def stats():
    """The three numbers on the dashboard (Pending Requests comes from the queue)."""
    today = clock.now().date()
    conn = get_db()
    try:
        borrows_today = conn.execute(
            "SELECT COUNT(*) FROM Borrow WHERE BorrowDate = ? AND Status IN ('Borrowed', 'Returned')",
            (today.isoformat(),),
        ).fetchone()[0]
        returns_today = conn.execute(
            """SELECT COUNT(*) FROM "Return" WHERE Status = 'Approved' AND ReturnDate = ?""",
            (today.isoformat(),),
        ).fetchone()[0]
        overdue = len(overdue_loans(conn, today, load_nonworking(conn)))
    finally:
        conn.close()
    return jsonify(borrows_today=borrows_today, returns_today=returns_today, overdue=overdue)


@librarian_bp.get("/overdue")
@librarian_required
def overdue():
    """The dashboard's Overdue Books table."""
    conn = get_db()
    try:
        return jsonify(overdue_loans(conn, clock.now().date(), load_nonworking(conn)))
    finally:
        conn.close()


HISTORY_SQL = """
    SELECT h.type, h.request_id, h.BorrowID, h.StudentID, h.BookID, h.RequestedAt,
           h.Status, h.LibrarianID,
           s.LastName, s.FirstName, s.MiddleInitial, bk.BookTitle
    FROM (
        SELECT 'borrow' AS type, b.BorrowID AS request_id, b.BorrowID, b.StudentID, b.BookID,
               b.RequestedAt,
               CASE b.Status WHEN 'Denied' THEN 'Denied' ELSE 'Approved' END AS Status,
               b.LibrarianID
        FROM Borrow AS b
        WHERE b.Status IN ('Borrowed', 'Returned', 'Denied')

        UNION ALL

        SELECT 'renew', r.RenewID, r.BorrowID, b.StudentID, b.BookID,
               r.RequestedAt, r.Status, r.LibrarianID
        FROM Renew AS r
        JOIN Borrow AS b ON b.BorrowID = r.BorrowID
        WHERE r.Status IN ('Approved', 'Denied')

        UNION ALL

        SELECT 'return', rt.ReturnID, rt.BorrowID, b.StudentID, b.BookID,
               rt.RequestedAt, rt.Status, rt.LibrarianID
        FROM "Return" AS rt
        JOIN Borrow AS b ON b.BorrowID = rt.BorrowID
        WHERE rt.Status IN ('Approved', 'Denied')
    ) AS h
    JOIN Student AS s ON s.StudentID = h.StudentID
    JOIN Book AS bk ON bk.BookID = h.BookID
    {where}
    ORDER BY h.RequestedAt DESC, h.type, h.request_id DESC
    LIMIT ?
"""


@librarian_bp.get("/history")
@librarian_required
def history():
    """Requests a librarian has already decided, newest request first.

    Status is Approved or Denied for all three types (an approved borrow that is
    still out or already returned both read as Approved). Optional ?type= and ?limit=.
    """
    type_filter = request.args.get("type", "").strip() or None
    if type_filter is not None and type_filter not in REQUEST_TYPES:
        return jsonify(ok=False, error="Unknown request type"), 400

    raw_limit = request.args.get("limit", "").strip()
    if raw_limit and not raw_limit.isdigit():
        return jsonify(ok=False, error="limit must be a whole number"), 400
    limit = min(max(int(raw_limit), 1), HISTORY_MAX_LIMIT) if raw_limit else HISTORY_DEFAULT_LIMIT

    where, params = ("WHERE h.type = ?", [type_filter]) if type_filter else ("", [])
    conn = get_db()
    try:
        rows = conn.execute(HISTORY_SQL.format(where=where), params + [limit]).fetchall()
    finally:
        conn.close()

    return jsonify([
        {
            "type": r["type"],
            "request_id": r["request_id"],
            "BorrowID": r["BorrowID"],
            "StudentID": r["StudentID"],
            "StudentName": _student_name(r),
            "BookID": r["BookID"],
            "BookTitle": r["BookTitle"],
            "RequestedAt": r["RequestedAt"],
            "Status": r["Status"],
            "LibrarianID": r["LibrarianID"],
        }
        for r in rows
    ])
