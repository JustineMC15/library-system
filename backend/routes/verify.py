from datetime import date

from flask import Blueprint, jsonify, request, session

import clock
from borrowing import (
    ALLOWED_DENY_REASONS,
    approve_borrow,
    deny_borrow,
    earlier_pending_count,
    get_queue,
)
from calendar_db import load_nonworking
from checks import run_checks
from db import get_db
from decorators import librarian_required
from routes.helpers import CHECK_ORDER, json_body

verify_bp = Blueprint("verify", __name__, url_prefix="/api/librarian")

REQUEST_TYPES = ("borrow", "renew", "return")

# These routes answer 501 until renew and return are created
NOT_READY = ({"ok": False, "error": "Only borrow requests are supported so far"}, 501)


def _check_type(req_type):
    """None when the type can be handled here, otherwise the (body, status) to send back."""
    if req_type not in REQUEST_TYPES:
        return {"ok": False, "error": "Unknown request type"}, 404
    if req_type != "borrow":
        return NOT_READY
    return None


def _full_name(row):
    middle = f" {row['MiddleInitial']}." if row["MiddleInitial"] else ""
    return f"{row['LastName']}, {row['FirstName']}{middle}"


def _age(date_of_birth: str, today: date) -> int:
    born = date.fromisoformat(date_of_birth)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


@verify_bp.get("/queue")
@librarian_required
def queue():
    """Every pending request, oldest first. earlier_pending = how many requests are ahead of it."""
    type_filter = request.args.get("type", "").strip() or None
    if type_filter is not None and type_filter not in REQUEST_TYPES:
        return jsonify(ok=False, error="Unknown request type"), 400

    conn = get_db()
    try:
        full_queue = get_queue(conn)
        students = {
            r["StudentID"]: _full_name(r)
            for r in conn.execute("SELECT StudentID, LastName, FirstName, MiddleInitial FROM Student")
        }
        titles = {r["BookID"]: r["BookTitle"] for r in conn.execute("SELECT BookID, BookTitle FROM Book")}
    finally:
        conn.close()

    result = []
    for position, item in enumerate(full_queue):
        if type_filter is not None and item["type"] != type_filter:
            continue
        item["StudentName"] = students.get(item["StudentID"])
        item["BookTitle"] = titles.get(item["BookID"])
        item["earlier_pending"] = position
        result.append(item)
    return jsonify(result)


@verify_bp.get("/request/<req_type>/<int:req_id>")
@librarian_required
def request_detail(req_type, req_id):
    """Everything the Verify page shows: student, book, queue position and the five checks."""
    blocked = _check_type(req_type)
    if blocked:
        return jsonify(blocked[0]), blocked[1]

    conn = get_db()
    try:
        borrow = conn.execute(
            """
            SELECT b.BorrowID, b.StudentID, b.RequestedAt, b.Status,
                   bk.BookID, bk.BookTitle, bk.BookAuthor, bk.BookType
            FROM Borrow AS b
            JOIN Book AS bk ON bk.BookID = b.BookID
            WHERE b.BorrowID = ?
            """,
            (req_id,),
        ).fetchone()
        if borrow is None:
            return jsonify(ok=False, error="Request not found"), 404

        student = conn.execute(
            """
            SELECT StudentID, LastName, FirstName, MiddleInitial, Address, DateOfBirth, Status
            FROM Student WHERE StudentID = ?
            """,
            (borrow["StudentID"],),
        ).fetchone()
        contacts = [
            r["ContactNo"]
            for r in conn.execute(
                "SELECT ContactNo FROM StudentContact WHERE StudentID = ? ORDER BY ContactNo",
                (borrow["StudentID"],),
            )
        ]

        today = clock.now().date()
        checks = run_checks(conn, borrow["StudentID"], today, load_nonworking(conn))
        earlier = earlier_pending_count(get_queue(conn), "borrow", req_id)   # None unless Pending
    finally:
        conn.close()

    check_list = []
    for name in CHECK_ORDER:
        if name == "No valid Student ID":
            # the system cannot work this one out: the librarian confirms it against the physical ID
            check_list.append({"name": name, "failed": None, "auto": False})
        else:
            check_list.append({"name": name, "failed": checks[name], "auto": True})

    return jsonify(
        ok=True,
        type="borrow",
        request_id=borrow["BorrowID"],
        status=borrow["Status"],
        requested_at=borrow["RequestedAt"],
        earlier_pending=earlier,
        student={
            "StudentID": student["StudentID"],
            "Name": _full_name(student),
            "Age": _age(student["DateOfBirth"], today),
            "Address": student["Address"],
            "Contacts": contacts,
            "Status": student["Status"],
        },
        book={
            "BookID": borrow["BookID"],
            "BookTitle": borrow["BookTitle"],
            "BookAuthor": borrow["BookAuthor"],
            "BookType": borrow["BookType"],
        },
        checks=check_list,
        any_failed=any(checks.values()),
    )


def _borrow_exists(conn, borrow_id):
    return conn.execute("SELECT 1 FROM Borrow WHERE BorrowID = ?", (borrow_id,)).fetchone() is not None


@verify_bp.post("/<req_type>/<int:req_id>/approve")
@librarian_required
def approve(req_type, req_id):
    """Approve a pending request. The server re-runs the checks, so a stale page cannot slip one through."""
    blocked = _check_type(req_type)
    if blocked:
        return jsonify(blocked[0]), blocked[1]

    student_id_ok = json_body().get("student_id_ok") is True   # only a real true counts

    conn = get_db()
    try:
        if not _borrow_exists(conn, req_id):
            return jsonify(ok=False, error="Request not found"), 404
        result = approve_borrow(
            conn, req_id, session["user_id"], clock.now().date(), load_nonworking(conn), student_id_ok
        )
        if not result["ok"]:
            return jsonify(result), 409
        conn.commit()
        return jsonify(result)
    finally:
        conn.close()


@verify_bp.post("/<req_type>/<int:req_id>/deny")
@librarian_required
def deny(req_type, req_id):
    """Deny a pending request. Body: {"reasons": [...]}, one saved row per reason."""
    blocked = _check_type(req_type)
    if blocked:
        return jsonify(blocked[0]), blocked[1]

    reasons = json_body().get("reasons")
    if not isinstance(reasons, list) or not reasons:
        return jsonify(ok=False, error="At least one denial reason is required"), 400
    if any(not isinstance(r, str) or r not in ALLOWED_DENY_REASONS for r in reasons):
        return jsonify(ok=False, error="Invalid denial reason"), 400

    conn = get_db()
    try:
        if not _borrow_exists(conn, req_id):
            return jsonify(ok=False, error="Request not found"), 404
        result = deny_borrow(conn, req_id, session["user_id"], reasons)
        if not result["ok"]:
            return jsonify(result), 409
        return jsonify(result)
    finally:
        conn.close()
