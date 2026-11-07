from flask import Blueprint, jsonify, session
from db import get_db
from decorators import student_required

requests_bp = Blueprint("requests", __name__, url_prefix="/api")

@requests_bp.get("/student/loans")
@student_required
def student_loans():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT Borrow.BorrowID, Borrow.BookID, Book.BookTitle, Book.BookAuthor,
               Borrow.Status, Borrow.BorrowDate,
               CASE WHEN Borrow.Status = 'Borrowed' THEN Book.DigitalLink END AS DigitalLink
        FROM Borrow
        JOIN Book ON Book.BookID = Borrow.BookID
        WHERE Borrow.StudentID = ?
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])