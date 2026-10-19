from flask import Blueprint, jsonify
from db import get_db

books_bp = Blueprint("books", __name__, url_prefix="/api")


@books_bp.route("/books")
def list_books():
    conn = get_db()
    rows = conn.execute("SELECT * FROM Book ORDER BY BookTitle").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])
