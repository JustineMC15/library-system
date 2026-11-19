from flask import Blueprint, jsonify, session

import clock
from calendar_db import load_nonworking
from db import get_db
from decorators import student_required
from loans import student_loans

requests_bp = Blueprint("requests", __name__, url_prefix="/api")


@requests_bp.get("/student/loans")
@student_required
def my_loans():
    conn = get_db()
    try:
        return jsonify(student_loans(conn, session["user_id"], clock.now().date(), load_nonworking(conn)))
    finally:
        conn.close()

@requests_bp.get("/student/history")
@student_required
def my_history():
    """Books the student has finished with, newest return first (the History tab)."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT b.BorrowID, b.BookID, bk.BookTitle, bk.BookType, b.BorrowDate,
                   rt.ReturnDate, b.Status,
                   COALESCE(rt.FineAmount, 0) AS FineAmount, rt.FinePaidDate
            FROM Borrow AS b
            JOIN Book AS bk ON bk.BookID = b.BookID
            LEFT JOIN "Return" AS rt ON rt.BorrowID = b.BorrowID AND rt.Status = 'Approved'
            WHERE b.StudentID = ? AND b.Status = 'Returned'
            ORDER BY rt.ReturnDate DESC, b.BorrowID DESC
            """,
            (session["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])