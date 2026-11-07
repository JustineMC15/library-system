from flask import Blueprint, jsonify, session

import clock
from borrowing import request_borrow
from db import get_db
from decorators import student_required
from routes.helpers import CHECK_ORDER, json_body, pick

borrow_bp = Blueprint("borrow", __name__, url_prefix="/api")


@borrow_bp.post("/borrow")
@student_required
def borrow():
    """A student asks to borrow a book. It is saved as Pending and waits for a librarian."""
    book_id = pick(json_body(), "BookID", "book_id")
    if not isinstance(book_id, str) or not book_id.strip():
        return jsonify(ok=False, error="BookID is required"), 400

    conn = get_db()
    try:
        result = request_borrow(conn, session["user_id"], book_id.strip(), clock.now())
        if not result["ok"]:
            status = 404 if result["error"] == "Book does not exist" else 409
            return jsonify(result), status
        conn.commit()
        return jsonify(result), 201
    finally:
        conn.close()


@borrow_bp.get("/student/denied")
@student_required
def student_denied():
    """The student's denied borrow requests, newest first, each with every reason that applies."""
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT b.BorrowID, b.BookID, bk.BookTitle, bk.BookAuthor, b.RequestedAt
            FROM Borrow AS b
            JOIN Book AS bk ON bk.BookID = b.BookID
            WHERE b.StudentID = ? AND b.Status = 'Denied'
            ORDER BY b.RequestedAt DESC, b.BorrowID DESC
            """,
            (session["user_id"],),
        ).fetchall()

        reasons = {}
        for r in conn.execute(
            """
            SELECT d.BorrowID, d.Reason
            FROM DenyReason AS d
            JOIN Borrow AS b ON b.BorrowID = d.BorrowID
            WHERE b.StudentID = ? AND b.Status = 'Denied'
            """,
            (session["user_id"],),
        ):
            reasons.setdefault(r["BorrowID"], []).append(r["Reason"])
    finally:
        conn.close()

    result = []
    for row in rows:
        item = dict(row)
        item["reasons"] = sorted(reasons.get(row["BorrowID"], []), key=CHECK_ORDER.index)
        result.append(item)
    return jsonify(result)
