from flask import Blueprint, jsonify, request
from db import get_db

books_bp = Blueprint("books", __name__, url_prefix="/api")


@books_bp.route("/books")
def list_books():
    search = request.args.get("search", "").strip()
    book_type = request.args.get("type", "").strip()
    year = request.args.get("year", "").strip()

    sql = "SELECT * FROM Book WHERE 1=1"
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

    sql += " ORDER BY BookTitle"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])