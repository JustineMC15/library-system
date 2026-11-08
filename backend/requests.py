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
