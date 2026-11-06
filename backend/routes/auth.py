from flask import Blueprint, request, session, jsonify
from werkzeug.security import check_password_hash
from db import get_db

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    role = data.get("role")                    # "student" or "librarian"
    user_id = str(data.get("id", "")).strip()
    password = data.get("password", "")

    conn = get_db()
    try:
        if role == "student":
            row = conn.execute(
                "SELECT StudentID AS id, PasswordHash, Status FROM Student WHERE StudentID = ?",
                (user_id,),
            ).fetchone()
        elif role == "librarian":
            row = conn.execute(
                "SELECT LibrarianID AS id, PasswordHash FROM Librarian WHERE LibrarianID = ?",
                (user_id,),
            ).fetchone()
        else:
            return jsonify(ok=False, error="Invalid role"), 400
    finally:
        conn.close()

    if row is None or not check_password_hash(row["PasswordHash"], password):
        return jsonify(ok=False, error="Invalid ID or password"), 401
    if role == "student" and row["Status"] == "Suspended":
        return jsonify(ok=False, error="Account suspended"), 403

    session.clear()
    session["user_id"] = row["id"]
    session["role"] = role
    return jsonify(ok=True, id=row["id"], role=role)


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@auth_bp.get("/me")
def me():
    if "user_id" not in session:
        return jsonify(ok=False, error="Not logged in"), 401
    return jsonify(ok=True, id=session["user_id"], role=session["role"])