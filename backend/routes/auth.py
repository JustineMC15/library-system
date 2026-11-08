import sqlite3
from datetime import date
from flask import Blueprint, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db


auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    role = data.get("role")                    # "student" or "librarian"
    user_id = str(data.get("id", "")).strip()
    password = str(data.get("password", ""))

    conn = get_db()
    try:
        if role == "student":
            row = conn.execute(
                "SELECT StudentID AS id, PasswordHash FROM Student WHERE StudentID = ?",
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

    # Suspended students can still log in. The librarian denies requests instead.
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
    conn = get_db()
    try:
        if session.get("role") == "student":
            row = conn.execute(
                "SELECT FirstName, LastName, MiddleInitial, Status FROM Student WHERE StudentID = ?",
                (session["user_id"],),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT LibrarianName FROM Librarian WHERE LibrarianID = ?",
                (session["user_id"],),
            ).fetchone()
    finally:
        conn.close()
    if row is None:                      # the account no longer exists
        session.clear()
        return jsonify(ok=False, error="Not logged in"), 401
    return jsonify(ok=True, id=session["user_id"], role=session["role"], **dict(row))


def _clean_contacts(raw):
    """Returns (set_of_numbers, error_message)."""
    if raw is None:
        return set(), None
    if not isinstance(raw, list):
        return None, "contact_numbers must be a list"
    numbers = {str(n).strip() for n in raw if n is not None}
    numbers.discard("")
    return numbers, None


@auth_bp.post("/register")
def register():
    d = request.get_json(silent=True) or {}
    sid = str(d.get("student_id", "")).strip()
    last = str(d.get("last_name", "")).strip()
    first = str(d.get("first_name", "")).strip()
    dob = str(d.get("date_of_birth", "")).strip()
    password = str(d.get("password", ""))
    middle = str(d.get("middle_initial") or "").strip()[:1].upper() or None
    address = str(d.get("address") or "").strip() or None

    if not all([sid, last, first, dob, password]):
        return jsonify(ok=False, error="Missing required fields"), 400

    try:
        if len(dob) != 10:
            raise ValueError
        dob_date = date.fromisoformat(dob)
    except ValueError:
        return jsonify(ok=False, error="date_of_birth must be a valid date (YYYY-MM-DD)"), 400
    if dob_date > date.today():
        return jsonify(ok=False, error="date_of_birth cannot be in the future"), 400

    contacts, err = _clean_contacts(d.get("contact_numbers"))
    if err:
        return jsonify(ok=False, error=err), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO Student (StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, PasswordHash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, last, first, middle, address, dob, generate_password_hash(password)),
        )
        conn.executemany(
            "INSERT INTO StudentContact (StudentID, ContactNo) VALUES (?, ?)",
            [(sid, n) for n in sorted(contacts)],
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "Student.StudentID" in str(e):
            return jsonify(ok=False, error="Student ID already registered"), 409
        raise
    finally:
        conn.close()
    return jsonify(ok=True), 201


@auth_bp.post("/librarian/register")
def register_librarian():
    d = request.get_json() or {}
    lid = str(d.get("librarian_id", "")).strip()
    name = str(d.get("librarian_name", "")).strip()
    password = str(d.get("password", ""))

    if not all([lid, name, password]):
        return jsonify(ok=False, error="Missing required fields"), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO Librarian (LibrarianID, LibrarianName, PasswordHash) VALUES (?, ?, ?)",
            (lid, name, generate_password_hash(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "Librarian.LibrarianID" in str(e):
            return jsonify(ok=False, error="Librarian ID already registered"), 409
        raise
    finally:
        conn.close()
    return jsonify(ok=True), 201