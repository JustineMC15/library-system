from datetime import date

from flask import Blueprint, jsonify, session

import clock
from calendar_db import load_nonworking
from checks import run_checks
from db import get_db
from decorators import librarian_required, student_required
from loans import get_due_date
from renewals import request_renew
from returns import (
    fine_owed,
    pay_fine,
    pay_student_fines,
    process_return,
    request_return,
)
from routes.helpers import json_body, pick, whole_number

renew_return_bp = Blueprint("renew_return", __name__, url_prefix="/api")


def _status_for(error: str) -> int:
    """404 for the "... not found" errors, 409 for everything else."""
    return 404 if "not found" in error else 409


# ---------- student: ask to renew or return ----------

@renew_return_bp.post("/renew")
@student_required
def renew():
    """A student asks to renew a borrowed book. It waits for a librarian."""
    borrow_id = whole_number(pick(json_body(), "BorrowID", "borrow_id"))
    if borrow_id is None:
        return jsonify(ok=False, error="BorrowID is required"), 400

    conn = get_db()
    try:
        result = request_renew(conn, session["user_id"], borrow_id, clock.now(), load_nonworking(conn))
        if not result["ok"]:
            return jsonify(result), _status_for(result["error"])
        conn.commit()
        return jsonify(result), 201
    finally:
        conn.close()


@renew_return_bp.post("/return")
@student_required
def return_book():
    """A student asks to return an e-book. Physical books go back at the library desk."""
    borrow_id = whole_number(pick(json_body(), "BorrowID", "borrow_id"))
    if borrow_id is None:
        return jsonify(ok=False, error="BorrowID is required"), 400

    conn = get_db()
    try:
        book = conn.execute(
            """
            SELECT bk.BookType
            FROM Borrow AS b
            JOIN Book AS bk ON bk.BookID = b.BookID
            WHERE b.BorrowID = ? AND b.StudentID = ? AND b.Status = 'Borrowed'
            """,
            (borrow_id, session["user_id"]),
        ).fetchone()
        # No row means not this student's loan: request_return answers "not found" (404)
        if book is not None and book["BookType"] != "Digital":
            return jsonify(ok=False, error="Physical books are returned at the library desk"), 409

        result = request_return(conn, session["user_id"], borrow_id, clock.now())
        if not result["ok"]:
            return jsonify(result), _status_for(result["error"])
        conn.commit()
        return jsonify(result), 201
    finally:
        conn.close()


# ---------- librarian: Process Return, fines, one student ----------

@renew_return_bp.post("/librarian/returns")
@librarian_required
def process_return_route():
    """Process a physical return at the desk. Body: {"BorrowID": 5, "ReturnDate": "2026-11-03"}.
    ReturnDate defaults to today and can't be in the future."""
    body = json_body()
    borrow_id = whole_number(pick(body, "BorrowID", "borrow_id"))
    if borrow_id is None:
        return jsonify(ok=False, error="BorrowID is required"), 400

    today = clock.now().date()
    raw_date = pick(body, "ReturnDate", "return_date")
    if raw_date is None:
        return_date = today
    else:
        try:
            return_date = date.fromisoformat(raw_date) if isinstance(raw_date, str) else None
        except ValueError:
            return_date = None
        if return_date is None:
            return jsonify(ok=False, error="ReturnDate must be a date like 2026-11-03"), 400
    if return_date > today:
        return jsonify(ok=False, error="The return date can't be in the future"), 400

    conn = get_db()
    try:
        result = process_return(conn, borrow_id, session["user_id"], return_date, load_nonworking(conn))
        if not result["ok"]:
            return jsonify(result), _status_for(result["error"])
        conn.commit()
        return jsonify(result)
    finally:
        conn.close()


@renew_return_bp.post("/librarian/fine/<int:return_id>/paid")
@librarian_required
def fine_paid(return_id):
    """Mark one return's fine as paid."""
    conn = get_db()
    try:
        result = pay_fine(conn, return_id, clock.now().date())
        if not result["ok"]:
            return jsonify(result), _status_for(result["error"])
        conn.commit()
        return jsonify(result)
    finally:
        conn.close()


@renew_return_bp.post("/librarian/students/<student_id>/pay-fines")
@librarian_required
def pay_fines(student_id):
    """Mark every unpaid fine of this student as paid (the Verify page's Mark as paid button)."""
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM Student WHERE StudentID = ?", (student_id,)).fetchone() is None:
            return jsonify(ok=False, error="Student not found"), 404
        result = pay_student_fines(conn, student_id, clock.now().date())
        if result["paid_count"] == 0:
            return jsonify(ok=False, error="This student has no unpaid fines"), 409
        conn.commit()
        return jsonify(result)
    finally:
        conn.close()


@renew_return_bp.get("/librarian/students/<student_id>")
@librarian_required
def student_detail(student_id):
    """One student for the Verify and Process Return pages.

    loans = books they hold now, each with its DueDate (and ReturnRequestedAt when a
    return is waiting). pending = their pending borrow requests. checks = the four
    checks the system can work out (true means the student fails it).
    """
    conn = get_db()
    try:
        student = conn.execute(
            """
            SELECT StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, Status
            FROM Student WHERE StudentID = ?
            """,
            (student_id,),
        ).fetchone()
        if student is None:
            return jsonify(ok=False, error="Student not found"), 404

        today = clock.now().date()
        nonworking = load_nonworking(conn)

        contacts = [
            r["ContactNo"]
            for r in conn.execute(
                "SELECT ContactNo FROM StudentContact WHERE StudentID = ? ORDER BY ContactNo",
                (student_id,),
            )
        ]

        loans = []
        for r in conn.execute(
            """
            SELECT b.BorrowID, b.BookID, bk.BookTitle, b.BorrowDate,
                   (SELECT rt.RequestedAt FROM "Return" AS rt
                     WHERE rt.BorrowID = b.BorrowID AND rt.Status = 'Pending') AS ReturnRequestedAt
            FROM Borrow AS b
            JOIN Book AS bk ON bk.BookID = b.BookID
            WHERE b.StudentID = ? AND b.Status = 'Borrowed'
            ORDER BY b.BorrowDate, b.BorrowID
            """,
            (student_id,),
        ):
            loan = dict(r)
            loan["DueDate"] = get_due_date(conn, r["BorrowID"], nonworking).isoformat()
            loans.append(loan)

        pending = [
            dict(r)
            for r in conn.execute(
                """
                SELECT b.BorrowID, b.BookID, bk.BookTitle, bk.BookType, b.BorrowDate,
                FROM Borrow AS b
                JOIN Book AS bk ON bk.BookID = b.BookID
                WHERE b.StudentID = ? AND b.Status = 'Pending'
                ORDER BY b.RequestedAt, b.BorrowID
                """,
                (student_id,),
            )
        ]

        data = dict(student)
        data["contacts"] = contacts
        data["FineOwed"] = fine_owed(conn, student_id)
        data["checks"] = run_checks(conn, student_id, today, nonworking)
        data["loans"] = loans
        data["pending"] = pending
        return jsonify(data)
    finally:
        conn.close()
