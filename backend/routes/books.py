from flask import Blueprint, jsonify, request, session
from db import get_db

books_bp = Blueprint("books", __name__, url_prefix="/api")

BOOK_COLUMNS = "BookID, BookISBN, BookTitle, BookAuthor, PublishYear, BookType"

AVAILABLE_SQL = (
    "NOT EXISTS (SELECT 1 FROM Borrow "
    "WHERE Borrow.BookID = Book.BookID AND Borrow.Status IN ('Pending', 'Borrowed'))"
)


def _select_columns():
    cols = BOOK_COLUMNS
    if session.get("role") == "librarian":      # only librarians see the e-book link here
        cols += ", DigitalLink"
    return f"{cols}, {AVAILABLE_SQL} AS available"


@books_bp.route("/books")
def list_books():
    search = request.args.get("search", "").strip()
    book_type = request.args.get("type", "").strip()
    year = request.args.get("year", "").strip()
    available = request.args.get("available", "").strip()

    sql = f"SELECT {_select_columns()} FROM Book WHERE 1=1"
    params = []

    if search:
        sql += " AND (BookTitle LIKE ? OR BookAuthor LIKE ? OR BookISBN LIKE ? OR BookID LIKE ?)"
        params += [f"%{search}%"] * 4

    if book_type in ("Physical", "Digital"):
        sql += " AND BookType = ?"
        params.append(book_type)

    if year.isdigit():
        sql += " AND PublishYear = ?"
        params.append(int(year))

    if available == "1":
        sql += f" AND {AVAILABLE_SQL}"

    sql += " ORDER BY BookTitle"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@books_bp.route("/books/<path:book_id>")
def get_book(book_id):
    conn = get_db()
    row = conn.execute(
        f"SELECT {_select_columns()} FROM Book WHERE BookID = ?", (book_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify(ok=False, error="Book not found"), 404
    return jsonify(dict(row))