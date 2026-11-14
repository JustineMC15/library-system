from datetime import date

from flask import Blueprint, jsonify, request

import clock
from calendar_db import load_nonworking
from db import get_db
from decorators import librarian_required
from loans import get_due_date
from working_days import days_overdue, fine

librarian_bp = Blueprint("librarian_dashboard", __name__, url_prefix="/api/librarian")

HISTORY_TYPES = ("borrow", "renew", "return")
HISTORY_LIMIT = 5000

def _student_names(conn):
    """StudentID -> 'Last, First M.' (same format as the queue)."""
    names = {}
    for r in conn.execute("SELECT StudentID, LastName, FirstName, MiddleInitial FROM Student"):
        middle = f" {r['MiddleInitial']}." if r["MiddleInitial"] else ""
        names[r["StudentID"]] = f"{r['LastName']}, {r['FirstName']}{middle}"
    return names


def _overdue_loans(conn, today, nonworking):
    """Every Borrowed loan that is past its due date today, most overdue first.

    "Unreturned books" in checks.py uses the same test (days overdue up to today).
    DaysLate and Fine stop at the day a pending return was requested, so they match
    what the student sees and what Process Return will charge.
    """
    names = _student_names(conn)
    rows = conn.execute(
        """
        SELECT b.BorrowID, b.StudentID, bk.BookTitle,
               (SELECT rt.RequestedAt FROM "Return" AS rt
                 WHERE rt.BorrowID = b.BorrowID AND rt.Status = 'Pending') AS ReturnRequestedAt
        FROM Borrow AS b
        JOIN Book AS bk ON bk.BookID = b.BookID
        WHERE b.Status = 'Borrowed'
        """
    ).fetchall()

    result = []
    for r in rows:
        due = get_due_date(conn, r["BorrowID"], nonworking)
        if days_overdue(due, today, nonworking) == 0:
            continue
        counted_until = date.fromisoformat(r["ReturnRequestedAt"][:10]) if r["ReturnRequestedAt"] else today
        late = days_overdue(due, counted_until, nonworking)
        result.append({
            "BorrowID": r["BorrowID"],
            "StudentID": r["StudentID"],
            "StudentName": names.get(r["StudentID"]),
            "BookTitle": r["BookTitle"],
            "DueDate": due.isoformat(),
            "DaysLate": late,
            "Fine": fine(late),
        })
    result.sort(key=lambda o: (-o["DaysLate"], o["DueDate"], o["BorrowID"]))
    return result


@librarian_bp.get("/stats")
@librarian_required
def stats():
    """The dashboard counters: books approved today, returns approved today, books overdue now."""
    today = clock.now().date()
    conn = get_db()
    try:
        borrows_today = conn.execute(
            "SELECT COUNT(*) FROM Borrow WHERE BorrowDate = ?", (today.isoformat(),)
        ).fetchone()[0]
        returns_today = conn.execute(
            'SELECT COUNT(*) FROM "Return" WHERE Status = \'Approved\' AND ReturnDate = ?',
            (today.isoformat(),),
        ).fetchone()[0]
        overdue = len(_overdue_loans(conn, today, load_nonworking(conn)))
    finally:
        conn.close()
    return jsonify(borrows_today=borrows_today, returns_today=returns_today, overdue=overdue)


@librarian_bp.get("/overdue")
@librarian_required
def overdue():
    """Overdue books for the dashboard table, most overdue first."""
    conn = get_db()
    try:
        return jsonify(_overdue_loans(conn, clock.now().date(), load_nonworking(conn)))
    finally:
        conn.close()


@librarian_bp.get("/history")
@librarian_required
def history():
    """Requests a librarian already decided (the History tab), newest decision first.

    Status is shown as Approved or Denied. A borrow that was approved is Borrowed or
    Returned in the Borrow table, and both mean Approved here. ?type=borrow|renew|return
    """
    type_filter = request.args.get("type", "").strip() or None
    if type_filter is not None and type_filter not in HISTORY_TYPES:
        return jsonify(ok=False, error="Unknown request type"), 400

    conn = get_db()
    try:
        names = _student_names(conn)
                rows = conn.execute(
            f"""
            SELECT h.*, l.LibrarianName
            FROM (
                SELECT 'borrow' AS type, b.BorrowID AS request_id, b.StudentID, b.BookID, bk.BookTitle,
                       b.RequestedAt,
                       substr(COALESCE(b.BorrowDate, b.RequestedAt), 1, 10) AS DecidedAt,
                       CASE b.Status WHEN 'Denied' THEN 'Denied' ELSE 'Approved' END AS Status,
                       b.LibrarianID
                FROM Borrow AS b
                JOIN Book AS bk ON bk.BookID = b.BookID
                WHERE b.Status != 'Pending'

                UNION ALL

                SELECT 'renew', r.RenewID, b.StudentID, b.BookID, bk.BookTitle,
                       r.RequestedAt,
                       substr(COALESCE(r.RenewalDate, r.RequestedAt), 1, 10),
                       r.Status, r.LibrarianID
                FROM Renew AS r
                JOIN Borrow AS b ON b.BorrowID = r.BorrowID
                JOIN Book AS bk ON bk.BookID = b.BookID
                WHERE r.Status != 'Pending'

                UNION ALL

                SELECT 'return', r.ReturnID, b.StudentID, b.BookID, bk.BookTitle,
                       r.RequestedAt,
                       substr(COALESCE(r.ReturnDate, r.RequestedAt), 1, 10),
                       r.Status, r.LibrarianID
                FROM "Return" AS r
                JOIN Borrow AS b ON b.BorrowID = r.BorrowID
                JOIN Book AS bk ON bk.BookID = b.BookID
                WHERE r.Status != 'Pending'
            ) AS h
            LEFT JOIN Librarian AS l ON l.LibrarianID = h.LibrarianID
            WHERE (:t IS NULL OR h.type = :t)
            ORDER BY h.DecidedAt DESC, h.RequestedAt DESC, h.type, h.request_id DESC
            LIMIT {HISTORY_LIMIT}
            """,
            {"t": type_filter},
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        item = dict(r)
        item["StudentName"] = names.get(item["StudentID"])
        result.append(item)
    return jsonify(result)
